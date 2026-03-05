import os
import sys
import time
import logging
from datetime import datetime
from tqdm import tqdm
import yaml

# 第三方库导入
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_openai import ChatOpenAI

# ================= 全局初始化 =================
def setup_logging(config):
    """配置日志系统"""
    log_dir = config['logging']['log_dir']
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 日志文件名包含时间戳
    log_filename = os.path.join(log_dir, f"agent_{datetime.now().strftime('%Y%m%d')}.log")
    
    # 配置日志格式
    logging.basicConfig(
        level=getattr(logging, config['logging']['level']),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout) # 同时输出到终端
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

# ================= 核心业务逻辑 =================
def save_archive_file(filename, content, logger):
    """保存归档文件"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"文件已成功保存: {filename}")
        return True
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        return False

def process_document(config, logger):
    """主处理流程"""
    start_time = time.time()
    pdf_path = config['document']['input_file']
    output_path = config['document']['output_file']

    # --------------------------------------------------
    # 阶段 1: 读取文档
    # --------------------------------------------------
    logger.info(f"开始处理文档: {pdf_path}")
    if not os.path.exists(pdf_path):
        logger.error(f"找不到输入文件: {pdf_path}")
        return False

    try:
        with tqdm(total=100, desc="整体进度", bar_format='{l_bar}{bar}| {n_fmt}%') as pbar:
            
            # --- 1.1 加载 PDF ---
            pbar.set_description("正在读取 PDF 文档")
            logger.info("正在加载 PDF 文档...")
            loader = PyMuPDFLoader(pdf_path)
            documents = loader.load()
            full_doc_text = "\n".join([doc.page_content for doc in documents])
            pbar.update(30) # 进度 30%
            logger.info(f"PDF 读取成功，共 {len(documents)} 页")

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
                logger.error(f"AI 服务初始化失败 (请检查 API Key): {e}")
                return False
            pbar.update(10) # 进度 40%

            # --- 1.3 构造 Prompt ---
            pbar.set_description("正在构造分析请求")
            # (为了代码简洁，这里的 Prompt 沿用之前的完美版本，你可以自行替换)
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
            pbar.update(10) # 进度 50%

            # --- 1.4 调用 AI 生成 ---
            pbar.set_description("AI 正在分析文档 (这可能需要一点时间)")
            logger.info("正在调用 AI 生成归档内容...")
            ai_start_time = time.time()
            
            ai_response = llm.invoke(archive_prompt)
            
            ai_duration = time.time() - ai_start_time
            logger.info(f"AI 生成完成，耗时: {ai_duration:.2f}秒")
            pbar.update(40) # 进度 90%

            # --- 1.5 保存文件 ---
            pbar.set_description("正在保存归档文件")
            if save_archive_file(output_path, ai_response.content, logger):
                pbar.update(10) # 进度 100%
                pbar.set_description("✅ 全部完成")
            else:
                return False

    except Exception as e:
        logger.error(f"处理过程中发生未预期的错误: {str(e)}", exc_info=True)
        return False

    # 统计总耗时
    total_duration = time.time() - start_time
    logger.info(f"="*50)
    logger.info(f"🎉 任务全部完成！总耗时: {total_duration:.2f}秒")
    logger.info(f"📁 输出文件: {output_path}")
    logger.info(f"="*50)
    return True

# ================= 程序入口 =================
if __name__ == "__main__":
    # 1. 加载配置
    config = load_config()
    
    # 2. 初始化日志
    logger = setup_logging(config)
    
    # 3. 打印欢迎信息
    print("\n" + "="*60)
    print("   硬件数据手册阅读 Agent (稳定版)")
    print("="*60 + "\n")
    
    # 4. 运行主流程
    success = process_document(config, logger)
    
    # 5. 退出码
    sys.exit(0 if success else 1)