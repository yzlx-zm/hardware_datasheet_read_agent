import os
import sys
import time
import logging
from datetime import datetime
from tqdm import tqdm
import yaml

# 第三方库导入
from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader, TextLoader
from langchain_openai import ChatOpenAI

# ================= 全局初始化 =================
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

# ================= 新增：智能文档加载器 =================
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
        logger.info(f"正在加载 {ext.upper()} 文档...")
        loader_class = loader_map[ext]
        
        # TextLoader需要指定编码
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

# ================= 新增：多格式归档保存器 =================
def save_archive_multi_format(content, base_name, config, logger):
    """保存为 Markdown/Word/Excel 多种格式"""
    # 1. 准备归档目录
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

    # --- 2. 保存 Markdown ---
    if "markdown" in formats:
        md_path = os.path.join(target_dir, f"{base_name}.md")
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"✅ Markdown 已保存: {md_path}")
            saved_files.append(md_path)
        except Exception as e:
            logger.error(f"保存 Markdown 失败: {e}")

    # --- 3. 保存 Word (.docx) ---
    if "word" in formats:
        docx_path = os.path.join(target_dir, f"{base_name}.docx")
        try:
            from docx import Document
            from docx.shared import Pt
            doc = Document()
            
            # 简单的样式设置
            title = doc.add_heading(base_name, 0)
            title.alignment = 1  # 居中
            
            # 按行处理内容，简单转换 (实际项目可使用 markdown2docx 库做完美转换)
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

    # --- 4. 保存 Excel (仅提取指令集和错误码表，后续可扩展) ---
    if "excel" in formats:
        xlsx_path = os.path.join(target_dir, f"{base_name}_指令集_错误码.xlsx")
        try:
            import pandas as pd
            
            # 创建一个Excel Writer
            with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
                # Sheet1: 说明
                df_info = pd.DataFrame({'说明': ['本文件由硬件文档Agent自动生成', f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}']})
                df_info.to_excel(writer, sheet_name='说明', index=False)
                
                # 这里可以通过正则或让AI返回JSON来提取表格
                # 为了演示稳定性，这里先留空Sheet，后续我们可以专门优化AI返回结构化数据
                df_placeholder = pd.DataFrame({'提示': ['完整的指令集和错误码表格提取功能开发中，敬请期待']})
                df_placeholder.to_excel(writer, sheet_name='指令集与错误码', index=False)
            
            logger.info(f"✅ Excel 已保存: {xlsx_path}")
            saved_files.append(xlsx_path)
        except ImportError:
            logger.warning("⚠️ 未安装 pandas/openpyxl 库，跳过 Excel 生成。请运行: pip install pandas openpyxl")
        except Exception as e:
            logger.error(f"保存 Excel 失败: {e}")

    return saved_files

# ================= 核心业务逻辑 =================
def process_document(config, logger):
    """主处理流程"""
    start_time = time.time()
    input_path = config['document']['input_file']
    output_base_name = config['document']['output_base_name']

    try:
        with tqdm(total=100, desc="整体进度", bar_format='{l_bar}{bar}| {n_fmt}%') as pbar:
            
            # --- 1.1 智能加载文档 ---
            pbar.set_description("正在读取文档")
            full_doc_text = load_document_smart(input_path, logger)
            if full_doc_text is None:
                return False
            pbar.update(30)

            # --- 1.2 初始化 LLM ---
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

            # --- 1.3 构造 Prompt ---
            pbar.set_description("正在构造分析请求")
            archive_prompt = f"""
            你是一名资深的嵌入式通信协议工程师。请基于提供的文档生成一份严谨的归档文档。
            【强制结构】
            # 3D人脸识别模组 通信协议归档文档
            ## 1. 文档概述
            ## 2. 物理层通信参数
            ## 3. 链路层数据帧结构 (表格)
            ## 4. 核心指令集汇总 (表格)
            ## 5. 校验算法定义
            ## 6. 模块全生命周期工作时序
            ## 7. 特殊时序与约束标记 (用【⚠️】开头)
            ## 8. 典型交互示例 (3个)
            ## 9. 错误码汇总表 (表格)
            【参考文档】
            {full_doc_text[:18000]}
            """
            pbar.update(10)

            # --- 1.4 调用 AI 生成 ---
            pbar.set_description("AI 正在分析文档")
            logger.info("正在调用 AI 生成归档内容...")
            ai_start_time = time.time()
            
            ai_response = llm.invoke(archive_prompt)
            
            ai_duration = time.time() - ai_start_time
            logger.info(f"AI 生成完成，耗时: {ai_duration:.2f}秒")
            pbar.update(40)

            # --- 1.5 多格式保存 ---
            pbar.set_description("正在保存归档文件")
            saved_files = save_archive_multi_format(ai_response.content, output_base_name, config, logger)
            
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
    config = load_config()
    logger = setup_logging(config)
    
    print("\n" + "="*60)
    print("   硬件数据手册阅读 Agent (多格式版)")
    print("="*60 + "\n")
    
    success = process_document(config, logger)
    sys.exit(0 if success else 1)