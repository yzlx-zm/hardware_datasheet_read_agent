import os
import sys
import time
import logging
import argparse
from datetime import datetime
from tqdm import tqdm
import yaml

from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader, TextLoader
from langchain_openai import ChatOpenAI
# 新增：长文档分块解析所需依赖，兼容新旧版LangChain
try:
    # 新版LangChain（0.2.x+）官方推荐路径
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    # 旧版LangChain兼容兜底路径
    from langchain.text_splitter import RecursiveCharacterTextSplitter
# token计数依赖
import tiktoken

# ================= 全局固定配置 =================
# 归档文档固定章节结构（与Prompt强制结构完全一致，用于去重、合并、校验）
ARCHIVE_CHAPTERS = [
    "1. 文档概述",
    "2. 物理层通信参数",
    "3. 链路层数据帧结构",
    "4. 核心指令集汇总",
    "5. 校验算法定义",
    "6. 模块全生命周期工作时序",
    "7. 特殊时序与约束标记",
    "8. 典型交互示例",
    "9. 错误码汇总表"
]
# 主标题匹配前缀
ARCHIVE_TITLE_PREFIX = "# "
# 二级章节匹配前缀
CHAPTER_PREFIX = "## "

# ================= 全局初始化 =================
def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='硬件数据手册解析归档 Agent')
    parser.add_argument(
        '-f', '--file', 
        type=str, 
        help='指定要解析的文档文件（支持相对input_dir的路径/绝对路径），优先级高于配置文件'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='指定输出文档的基础名称（不含后缀），优先级高于配置文件'
    )
    return parser.parse_args()

def setup_logging(config):
    """配置日志系统"""
    log_dir = config['logging']['log_dir']
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_filename = os.path.join(log_dir, f"agent_{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=getattr(logging, config['logging']['level']),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def load_config(config_path="config.yaml"):
    """加载配置文件"""
    if not os.path.exists(config_path):
        print(f"❌ 错误：找不到配置文件 {config_path}！")
        print(f"   请复制 config.yaml.example 为 config.yaml 并填入配置。")
        sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"❌ 配置文件格式错误: {e}")
            sys.exit(1)

# ================= 智能文档加载器 =================
def load_document_smart(file_path, logger):
    """根据文件后缀智能选择加载器"""
    if not os.path.exists(file_path):
        logger.error(f"找不到输入文件: {file_path}")
        return None

    ext = os.path.splitext(file_path)[1].lower()
    
    loader_map = {
        '.pdf': PyMuPDFLoader,
        '.docx': Docx2txtLoader,
        '.txt': TextLoader
    }

    if ext not in loader_map:
        logger.error(f"不支持的文件格式: {ext}，当前支持: {list(loader_map.keys())}")
        return None

    try:
        logger.info(f"正在加载 {ext.upper()} 文档: {os.path.basename(file_path)}")
        loader_class = loader_map[ext]
        
        if ext == '.txt':
            loader = loader_class(file_path, encoding='utf-8')
        else:
            loader = loader_class(file_path)
            
        documents = loader.load()
        full_text = "\n".join([doc.page_content for doc in documents])
        logger.info(f"文档加载成功，共 {len(documents)} 页/段")
        return full_text
    except Exception as e:
        logger.error(f"加载文档失败: {str(e)}", exc_info=True)
        return None

# ================= 表格解析辅助函数 =================
def extract_markdown_table(md_content: str, chapter_title: str, logger):
    """
    从Markdown内容中提取指定章节的表格，返回pandas.DataFrame
    适配AI生成的固定章节结构，异常场景自动兜底，新手友好
    :param md_content: AI生成的完整Markdown归档内容
    :param chapter_title: 要提取的章节标题（如"链路层数据帧结构"）
    :param logger: 日志对象
    :return: 提取成功返回DataFrame，失败返回None
    """
    try:
        # 1. 按换行拆分内容，逐行匹配目标章节
        lines = md_content.split('\n')
        chapter_found = False
        table_lines = []

        # 2. 匹配目标章节，捕获章节后的Markdown表格
        for line in lines:
            # 匹配目标章节标题（兼容# 层级、前后空格）
            if not chapter_found and chapter_title in line and line.startswith('#'):
                chapter_found = True
                continue
            # 找到章节后，开始捕获表格（以|开头的行是Markdown表格行）
            if chapter_found:
                # 遇到下一个章节标题，停止捕获（表格结束）
                if line.startswith('#'):
                    break
                # 只保留表格行
                if line.strip().startswith('|') and line.strip().endswith('|'):
                    table_lines.append(line.strip())
        
        # 兜底：未捕获到表格行
        if len(table_lines) < 2:
            logger.warning(f"⚠️ 章节【{chapter_title}】未找到有效表格，跳过")
            return None

        # 3. 清洗Markdown表格，转为标准CSV格式
        cleaned_rows = []
        for row in table_lines:
            # 去掉首尾的|，按|拆分单元格，去除每个单元格前后空格
            cells = [cell.strip() for cell in row[1:-1].split('|')]
            # 过滤Markdown表格的分隔行（---|---格式）
            if not all(cell.replace('-', '').strip() == '' for cell in cells):
                cleaned_rows.append(cells)
        
        # 兜底：清洗后无有效数据行
        if len(cleaned_rows) < 1:
            logger.warning(f"⚠️ 章节【{chapter_title}】表格清洗后无有效数据，跳过")
            return None

        # 4. 转为DataFrame返回
        import pandas as pd
        df = pd.DataFrame(cleaned_rows[1:], columns=cleaned_rows[0])
        logger.info(f"✅ 成功提取【{chapter_title}】表格，共{len(df)}条数据")
        return df

    except Exception as e:
        logger.error(f"❌ 提取【{chapter_title}】表格失败: {str(e)}", exc_info=True)
        return None

# ================= 长文档分块解析辅助函数 =================
def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """
    计算文本token数量，DeepSeek与OpenAI token计数规则完全兼容
    :param text: 待计算的文本内容
    :param model_name: 编码适配模型名称，默认兼容DeepSeek
    :return: 文本token数量
    """
    try:
        encoding = tiktoken.encoding_for_model(model_name)
        return len(encoding.encode(text))
    except Exception:
        # 兜底方案：按字符数估算（1token≈3个中英混合字符）
        return len(text) // 3
# ================= 归档内容合并与去重辅助函数 =================
def split_content_by_chapter(content: str) -> dict:
    """
    将生成的归档内容按固定章节拆分，返回「章节名: 章节内容」的字典，用于去重合并
    :param content: AI生成的单块/完整归档内容
    :return: 章节字典，key为章节名，value为章节完整内容
    """
    chapter_dict = {}
    current_chapter = None
    current_content = []

    lines = content.split('\n')
    for line in lines:
        # 匹配二级章节标题
        if line.startswith(CHAPTER_PREFIX):
            # 保存上一个章节的内容
            if current_chapter is not None:
                chapter_dict[current_chapter] = "\n".join(current_content).strip()
            # 开启新章节，仅保留固定章节列表内的章节
            chapter_title = line[len(CHAPTER_PREFIX):].strip()
            for standard_chapter in ARCHIVE_CHAPTERS:
                if standard_chapter in chapter_title:
                    current_chapter = standard_chapter
                    current_content = []
                    break
            else:
                current_chapter = None
                current_content = []
        # 非标题行，加入当前章节内容
        elif current_chapter is not None:
            current_content.append(line)
    
    # 保存最后一个章节
    if current_chapter is not None and current_content:
        chapter_dict[current_chapter] = "\n".join(current_content).strip()
    
    return chapter_dict

def merge_chapter_content(existing_dict: dict, new_dict: dict) -> dict:
    """
    增量合并章节内容，已有章节仅补充新内容，无内容的章节新增，彻底避免重复
    :param existing_dict: 已有的章节内容字典
    :param new_dict: 新生成的章节内容字典
    :return: 合并后的完整章节字典
    """
    merged_dict = existing_dict.copy()
    for chapter_name, new_content in new_dict.items():
        # 章节不存在：直接新增
        if chapter_name not in merged_dict:
            merged_dict[chapter_name] = new_content
        # 章节已存在：仅补充新内容，避免重复
        else:
            existing_content = merged_dict[chapter_name]
            # 逐行去重，仅添加原有内容里没有的新行
            new_lines = new_content.split('\n')
            for line in new_lines:
                line_stripped = line.strip()
                if line_stripped and line_stripped not in existing_content:
                    existing_content += "\n" + line
            merged_dict[chapter_name] = existing_content.strip()
    return merged_dict

def rebuild_full_content(title: str, chapter_dict: dict) -> str:
    """
    基于合并后的章节字典，重新生成结构完整、无重复的归档文档
    :param title: 文档主标题
    :param chapter_dict: 合并后的章节内容字典
    :return: 完整的Markdown归档内容
    """
    full_content = f"{ARCHIVE_TITLE_PREFIX}{title}\n\n"
    # 严格按照固定章节顺序生成，保证结构统一
    for chapter_name in ARCHIVE_CHAPTERS:
        if chapter_name in chapter_dict and chapter_dict[chapter_name].strip():
            full_content += f"{CHAPTER_PREFIX}{chapter_name}\n{chapter_dict[chapter_name]}\n\n"
    return full_content.strip()

def split_document_by_chapter(full_text: str, max_chunk_tokens: int = 28000, logger=None) -> list:
    """
    硬件文档专属智能分块：按章节标题拆分，保证单块token不超限、不拆分完整章节
    :param full_text: 完整的文档全文本
    :param max_chunk_tokens: 单块最大token数，预留20%余量给Prompt和模型输出
    :param logger: 日志对象
    :return: 分块后的文本列表
    """
    try:
        # 硬件手册专属分块规则：优先按二级/三级章节拆分，保证章节完整性
        text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
            chunk_size=max_chunk_tokens,  # 修复：直接传token上限，不再乘以3，与length_function单位完全匹配
            chunk_overlap=300,  # 优化：块间上下文重叠提升至300，避免长文档章节上下文断裂
            length_function=lambda x: count_tokens(x)
        )
        chunks = text_splitter.split_text(full_text)
        
        if logger:
            logger.info(f"📄 文档分块完成，共分为 {len(chunks)} 块，单块最大token上限: {max_chunk_tokens}")
            for i, chunk in enumerate(chunks):
                logger.info(f"  第{i+1}块 token数: {count_tokens(chunk)}")
        
        return chunks

    except Exception as e:
        if logger:
            logger.error(f"❌ 文档分块失败: {str(e)}，自动降级为单块解析模式", exc_info=True)
        # 异常兜底：返回原文本安全截断内容，保证程序正常运行
        safe_single_chunk = full_text[:max_chunk_tokens*3]
        if logger:
            logger.warning(f"⚠️  降级单块token数: {count_tokens(safe_single_chunk)}")
        return [safe_single_chunk]

# ================= 多格式归档保存器 =================
def save_archive_multi_format(content, base_name, config, logger):
    """保存为 Markdown/Word/Excel 多种格式"""
    archive_root = config['archive'].get('archive_root_dir', 'output_archive')
    if config['archive'].get('use_timestamp_folder', True):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target_dir = os.path.join(archive_root, f"{base_name}_{timestamp}")
    else:
        target_dir = archive_root

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    
    saved_files = []
    formats = config['document'].get('output_formats', ['markdown'])

    # 保存 Markdown
    if "markdown" in formats:
        md_path = os.path.join(target_dir, f"{base_name}.md")
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"✅ Markdown 已保存: {md_path}")
            saved_files.append(md_path)
        except Exception as e:
            logger.error(f"保存 Markdown 失败: {e}")

    # 保存 Word (.docx)
    if "word" in formats:
        docx_path = os.path.join(target_dir, f"{base_name}.docx")
        try:
            from docx import Document
            doc = Document()
            
            title = doc.add_heading(base_name, 0)
            title.alignment = 1
            
            for line in content.split('\n'):
                if line.startswith('# '):
                    doc.add_heading(line[2:], level=1)
                elif line.startswith('## '):
                    doc.add_heading(line[3:], level=2)
                elif line.startswith('### '):
                    doc.add_heading(line[4:], level=3)
                elif line.strip() == '':
                    continue
                else:
                    p = doc.add_paragraph(line)
                    p.paragraph_format.line_spacing = 1.5
            
            doc.save(docx_path)
            logger.info(f"✅ Word 文档已保存: {docx_path}")
            saved_files.append(docx_path)
        except ImportError:
            logger.warning("⚠️ 未安装 python-docx 库，跳过 Word 生成。请运行: pip install python-docx")
        except Exception as e:
            logger.error(f"保存 Word 失败: {e}")

    # 保存 Excel
    if "excel" in formats:
        xlsx_path = os.path.join(target_dir, f"{base_name}_指令集_错误码.xlsx")
        try:
            import pandas as pd
            
            with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
                # 1. 保留说明Sheet，补充完整生成信息
                df_info = pd.DataFrame({'说明': [
                    '本文件由硬件文档Agent自动生成', 
                    f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                    f'源文档: {base_name}',
                    '包含内容：数据帧结构、核心指令集、错误码汇总'
                ]})
                df_info.to_excel(writer, sheet_name='文档说明', index=False)

                # 2. 批量提取核心表格，写入对应Sheet
                # 定义要提取的章节与Sheet名映射（与AI生成的固定结构完全匹配）
                table_map = {
                    "链路层数据帧结构": "数据帧结构",
                    "核心指令集汇总": "核心指令集",
                    "错误码汇总表": "错误码汇总"
                }

                for chapter_title, sheet_name in table_map.items():
                    table_df = extract_markdown_table(content, chapter_title, logger)
                    if table_df is not None and not table_df.empty:
                        table_df.to_excel(writer, sheet_name=sheet_name, index=False)

            logger.info(f"✅ Excel 已保存: {xlsx_path}")
            saved_files.append(xlsx_path)
        except ImportError:
            logger.warning("⚠️ 未安装 pandas/openpyxl 库，跳过 Excel 生成。请运行: pip install pandas openpyxl")
        except Exception as e:
            logger.error(f"保存 Excel 失败: {e}")

        # 保存 CSV
    if "csv" in formats:
        try:
            import pandas as pd
            # 定义要提取的章节与CSV文件名映射
            table_map = {
                "链路层数据帧结构": "数据帧结构",
                "核心指令集汇总": "核心指令集",
                "错误码汇总表": "错误码汇总"
            }

            csv_saved_count = 0
            for chapter_title, file_suffix in table_map.items():
                csv_path = os.path.join(target_dir, f"{base_name}_{file_suffix}.csv")
                table_df = extract_markdown_table(content, chapter_title, logger)
                if table_df is not None and not table_df.empty:
                    # 用utf-8-sig编码，兼容Windows Excel打开不乱码
                    table_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                    logger.info(f"✅ CSV 已保存: {csv_path}")
                    saved_files.append(csv_path)
                    csv_saved_count += 1
            
            if csv_saved_count == 0:
                logger.warning("⚠️ 未提取到有效表格，无CSV文件生成")

        except ImportError:
            logger.warning("⚠️ 未安装 pandas 库，跳过 CSV 生成。请运行: pip install pandas")
        except Exception as e:
            logger.error(f"保存 CSV 失败: {e}")        

    return saved_files

# ================= 核心业务逻辑 =================
def process_document(config, input_file_path, output_base_name, logger):
    """主处理流程"""
    start_time = time.time()

    try:
        with tqdm(total=100, desc="整体进度", bar_format='{l_bar}{bar}| {n_fmt}%') as pbar:
            
            # 1. 智能加载文档
            pbar.set_description("正在读取文档")
            full_doc_text = load_document_smart(input_file_path, logger)
            if full_doc_text is None:
                return False
            pbar.update(30)

            # 2. 初始化 LLM
            pbar.set_description("正在初始化 AI 模型")
            logger.info("正在连接 AI 服务...")
            try:
                llm = ChatOpenAI(
                    model=config['llm']['model_name'],
                    api_key=config['llm']['api_key'],
                    base_url=config['llm']['base_url'],
                    temperature=config['llm']['temperature']
                )
            except Exception as e:
                logger.error(f"AI 服务初始化失败: {e}")
                return False
            pbar.update(10)

                        # 3. 文档token统计与分块处理（解决长文档截断核心问题）
            pbar.set_description("正在处理文档分块")
            # 模型上下文安全上限：DeepSeek-chat 32k上下文，预留4k给Prompt和输出，单块最大28k token
            max_single_chunk_tokens = 28000
            total_tokens = count_tokens(full_doc_text)
            logger.info(f"📄 文档总token数: {total_tokens}")
            
            # 短文档直接走单块逻辑，无额外性能开销
            if total_tokens <= max_single_chunk_tokens:
                document_chunks = [full_doc_text]
                logger.info("✅ 文档长度在安全范围内，采用单块解析模式")
            # 长文档按章节智能分块解析
            else:
                document_chunks = split_document_by_chapter(full_doc_text, max_single_chunk_tokens, logger)
                # 兜底：分块后仍有超上限的块，强制二次拆分，彻底杜绝超上限问题
                for i, chunk in reversed(list(enumerate(document_chunks))):
                    chunk_token = count_tokens(chunk)
                    if chunk_token > max_single_chunk_tokens:
                        logger.warning(f"⚠️  第{i+1}块token数{chunk_token}仍超上限，执行强制二次拆分")
                        sub_chunks = split_document_by_chapter(chunk, max_single_chunk_tokens//2, logger)
                        document_chunks.pop(i)
                        document_chunks[i:i] = sub_chunks
            pbar.update(5)

            # 4. 构造强约束Prompt模板（彻底解决重复生成问题）
            pbar.set_description("正在构造分析请求")
            base_prompt_template = f"""
            你是一名资深的嵌入式通信协议工程师。请严格遵循以下规则，基于文档片段补充完善归档文档。
            【绝对强制规则，违反则输出无效】
            1. 仅输出【缺失章节的内容】，绝对禁止重复生成【已生成的归档内容】中已有的章节和内容
            2. 仅当文档片段中包含对应章节的信息时，才生成该章节内容，无信息的章节绝对不要生成
            3. 严格遵循下方固定的9个章节结构，不得新增/删减章节，所有表格必须用标准Markdown格式
            4. 特殊时序与约束必须用【⚠️】开头标记，典型交互示例不少于3个
            5. 仅输出章节正文内容，不要输出任何解释、说明、道歉类话术
            【固定归档章节结构】
            # {output_base_name}
            ## 1. 文档概述
            ## 2. 物理层通信参数
            ## 3. 链路层数据帧结构 (表格)
            ## 4. 核心指令集汇总 (表格)
            ## 5. 校验算法定义
            ## 6. 模块全生命周期工作时序
            ## 7. 特殊时序与约束标记 (用【⚠️】开头)
            ## 8. 典型交互示例 (3个)
            ## 9. 错误码汇总表 (表格)
            【已生成的归档内容】
            {{generated_content}}
            【当前待解析的文档片段】
            {{document_chunk}}
            """
            pbar.update(5)

            # 5. 分块调用AI生成，增量合并内容（彻底解决重复堆叠问题）
            pbar.set_description("AI 正在分块解析文档")
            logger.info(f"开始分块生成归档内容，共 {len(document_chunks)} 个解析块")
            ai_start_time = time.time()
            
            # 初始化：用字典存储章节内容，替代简单字符串拼接，天然去重
            merged_chapter_dict = {}

            # 逐块解析，增量合并，单块失败不中断整体流程
            for chunk_index, chunk in enumerate(document_chunks):
                chunk_start_time = time.time()
                logger.info(f"▶️  正在解析第 {chunk_index+1}/{len(document_chunks)} 块")
                
                # 基于已合并的内容，生成当前块的Prompt
                current_generated_content = rebuild_full_content(output_base_name, merged_chapter_dict)
                current_prompt = base_prompt_template.format(
                    document_chunk=chunk,
                    generated_content=current_generated_content if current_generated_content else "无（首次生成，需输出所有有信息的章节内容）"
                )

                # 调用AI生成当前块内容
                try:
                    chunk_response = llm.invoke(current_prompt)
                    chunk_content = chunk_response.content.strip()
                    
                    # 解析当前块生成的章节内容，增量合并到总字典中
                    chunk_chapter_dict = split_content_by_chapter(chunk_content)
                    merged_chapter_dict = merge_chapter_content(merged_chapter_dict, chunk_chapter_dict)
                    
                    chunk_duration = time.time() - chunk_start_time
                    logger.info(f"✅ 第 {chunk_index+1}/{len(document_chunks)} 块解析完成，耗时: {chunk_duration:.2f}秒，新增/补充章节: {list(chunk_chapter_dict.keys())}")
                except Exception as e:
                    logger.error(f"❌ 第 {chunk_index+1} 块解析失败: {str(e)}，跳过当前块继续解析", exc_info=True)
                
                # 进度条更新：分块解析占35%总进度，与原有进度条体系完全兼容
                pbar.update(35 / len(document_chunks))

            # 6. 重新生成完整无重复的归档内容
            full_generated_content = rebuild_full_content(output_base_name, merged_chapter_dict)
            # 解析完成统计
            ai_duration = time.time() - ai_start_time
            logger.info(f"AI 全部分块解析完成，总耗时: {ai_duration:.2f}秒，最终生成完整章节: {list(merged_chapter_dict.keys())}")
            pbar.update(5)

            # 7. 多格式保存（修复：使用分块合并后的正确变量full_generated_content）
            pbar.set_description("正在保存归档文件")
            saved_files = save_archive_multi_format(full_generated_content, output_base_name, config, logger)
            
            if saved_files:
                pbar.update(10)
                pbar.set_description("✅ 全部完成")
            else:
                logger.warning("未成功保存任何文件")
                return False

    except Exception as e:
        logger.error(f"处理过程中发生未预期的错误: {str(e)}", exc_info=True)
        return False
    total_duration = time.time() - start_time
    logger.info(f"="*50)
    logger.info(f"🎉 任务全部完成！总耗时: {total_duration:.2f}秒")
    logger.info(f"📁 归档文件保存在: {config['archive'].get('archive_root_dir', 'output_archive')}")
    logger.info(f"="*50)
    return True

# ================= 程序入口 =================
if __name__ == "__main__":
    # 1. 解析命令行参数
    args = parse_args()
    
    # 2. 加载配置
    config = load_config()
    
    # 3. 初始化日志
    logger = setup_logging(config)
    
    # 4. 打印欢迎信息
    print("\n" + "="*60)
    print("   硬件数据手册解析归档 Agent (hw_datasheet_agent)")
    print("="*60 + "\n")
    
    # 5. 处理输入文件路径
    input_dir = config['document'].get('input_dir', 'input_docs')
    # 命令行指定的文件优先级最高
    if args.file:
        input_file_name = args.file
    else:
        input_file_name = config['document']['input_file']
    
    # 拼接完整路径：如果是绝对路径直接用，否则拼接input_dir
    if os.path.isabs(input_file_name):
        input_file_path = input_file_name
    else:
        input_file_path = os.path.join(input_dir, input_file_name)
    
    # 6. 生成最终的输出基础名称（优先级：命令行 > 配置文件 > 自动生成）
    # 提取输入文件的纯名称（不带路径和后缀）
    input_file_basename = os.path.splitext(os.path.basename(input_file_path))[0]
    # 优先级1：命令行指定的输出名称
    if args.output:
        final_output_base_name = args.output.strip()
    # 优先级2：配置文件里指定的名称
    elif config['document'].get('output_base_name', '').strip():
        final_output_base_name = config['document']['output_base_name'].strip()
    # 优先级3：自动根据输入文件名生成
    else:
        final_output_base_name = f"{input_file_basename}_通信协议归档"
    
    logger.info(f"待解析文档: {input_file_path}")
    logger.info(f"输出文档基础名称: {final_output_base_name}")
    
    # 7. 运行主流程（修复后正确逻辑）
    success = process_document(config, input_file_path, final_output_base_name, logger)
    sys.exit(0 if success else 1)