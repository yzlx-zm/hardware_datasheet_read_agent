# ================= 核心 Agent =================
"""
独立 Agent，具有自主决策能力
"""
import os
import sys
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI

from .state_manager import StateManager
from reviewer import DataReviewer, AuditReport
from config.constants import ARCHIVE_CHAPTERS, CHAPTER_PREFIX, ARCHIVE_TITLE_PREFIX


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    content: str = ""
    output_paths: List[str] = None
    audit_report: Optional[AuditReport] = None
    error: Optional[str] = None
    retry_count: int = 0

    def __post_init__(self):
        if self.output_paths is None:
            self.output_paths = []


class CoreAgent:
    """
    核心 Agent 类

    职责：
    1. 编排整个处理流程
    2. 决策：异常处理、重试策略
    3. 状态管理
    4. 触发审核
    """

    def __init__(self, config: Dict, logger: logging.Logger):
        """
        初始化 Agent

        Args:
            config: 配置字典
            logger: 日志对象
        """
        self.config = config
        self.logger = logger
        self.state = StateManager()
        self.reviewer = DataReviewer(config, logger)

        # 初始化 LLM
        llm_config = config.get('llm', {}).copy()
        self.llm = ChatOpenAI(**llm_config)

        # 审核配置
        review_config = config.get('review', {})
        self.enable_review = review_config.get('enabled', True)
        self.max_retries = review_config.get('max_retries', 2)

    def run(self, input_file: str, output_name: str,
            document_loader=None,
            text_splitter=None,
            content_processor=None,
            file_saver=None) -> AgentResult:
        """
        主执行流程

        Args:
            input_file: 输入文件路径
            output_name: 输出文件基础名称
            document_loader: 文档加载函数（可选，用于依赖注入）
            text_splitter: 文本分块函数（可选）
            content_processor: 内容处理函数（可选）
            file_saver: 文件保存函数（可选）

        Returns:
            AgentResult 执行结果
        """
        retry_count = 0

        while retry_count <= self.max_retries:
            try:
                # 1. 加载文档
                self.logger.info(f"正在加载文档: {input_file}")
                if document_loader:
                    raw_text = document_loader(input_file, self.logger)
                else:
                    raw_text = self._default_load_document(input_file)

                if raw_text is None:
                    return AgentResult(
                        success=False,
                        error="文档加载失败"
                    )

                # 保存原文到状态管理器
                self.state.store_original(raw_text, input_file)
                self.logger.info(f"文档加载成功，原文长度: {len(raw_text)} 字符")

                # 2. 分块处理
                self.logger.info("开始分块处理...")
                if text_splitter:
                    chunks = text_splitter(raw_text, self.config, self.logger)
                else:
                    chunks = self._default_split_document(raw_text)

                self.state.set_chunks(chunks)

                # 3. 逐块 LLM 处理
                if content_processor:
                    generated_content = content_processor(
                        chunks, output_name, self.llm, self.logger, self.state
                    )
                else:
                    generated_content = self._default_process_chunks(
                        chunks, output_name
                    )

                if not generated_content:
                    return AgentResult(
                        success=False,
                        error="内容生成失败"
                    )

                # 4. 深度审核（如果启用）
                audit_report = None
                if self.enable_review:
                    self.logger.info("开始深度审核...")
                    audit_report = self.reviewer.review(self.state)
                    self.state.audit_result = audit_report

                    if not audit_report.passed:
                        self.logger.warning(f"审核未通过: {audit_report.get_summary()}")

                        # 判断是否重试
                        if self.reviewer.should_retry(audit_report) and retry_count < self.max_retries:
                            retry_count += 1
                            self.logger.info(f"准备第 {retry_count} 次重试...")
                            # 重置状态
                            self.state = StateManager()
                            continue
                        elif not audit_report.can_retry:
                            self.logger.warning("审核问题不可通过重试修复")

                # 5. 保存输出
                self.logger.info("保存输出文件...")
                if file_saver:
                    output_paths = file_saver(
                        generated_content, output_name, self.config, self.logger,
                        audit_report=audit_report
                    )
                else:
                    output_paths = self._default_save_files(
                        generated_content, output_name, audit_report
                    )

                return AgentResult(
                    success=True,
                    content=generated_content,
                    output_paths=output_paths,
                    audit_report=audit_report,
                    retry_count=retry_count
                )

            except Exception as e:
                self.logger.error(f"Agent 执行异常: {str(e)}", exc_info=True)

                # 判断是否应该重试
                if self._should_retry(e) and retry_count < self.max_retries:
                    retry_count += 1
                    self.logger.info(f"异常后准备第 {retry_count} 次重试...")
                    self.state = StateManager()
                    continue
                else:
                    return AgentResult(
                        success=False,
                        error=str(e),
                        retry_count=retry_count
                    )

        # 超过最大重试次数
        return AgentResult(
            success=False,
            error=f"超过最大重试次数 ({self.max_retries})",
            retry_count=retry_count
        )

    def _should_retry(self, error: Exception) -> bool:
        """
        判断是否应该重试

        Args:
            error: 异常对象

        Returns:
            bool 是否应该重试
        """
        # 网络相关错误可以重试
        retryable_errors = [
            "ConnectionError",
            "TimeoutError",
            "APIConnectionError",
            "RateLimitError",
            "ServiceUnavailableError"
        ]

        error_type = type(error).__name__
        if error_type in retryable_errors:
            return True

        # 检查错误消息
        error_msg = str(error).lower()
        retryable_keywords = ["timeout", "connection", "rate limit", "unavailable"]
        if any(kw in error_msg for kw in retryable_keywords):
            return True

        return False

    def _default_load_document(self, file_path: str) -> Optional[str]:
        """默认文档加载（需要外部注入或覆写）"""
        # 这个方法会在主程序中被替换
        raise NotImplementedError("请通过参数注入 document_loader")

    def _default_split_document(self, text: str) -> List[str]:
        """默认分块（需要外部注入或覆写）"""
        raise NotImplementedError("请通过参数注入 text_splitter")

    def _default_process_chunks(self, chunks: List[str], output_name: str) -> str:
        """默认内容处理（需要外部注入或覆写）"""
        raise NotImplementedError("请通过参数注入 content_processor")

    def _default_save_files(self, content: str, output_name: str,
                           audit_report: Optional[AuditReport]) -> List[str]:
        """默认文件保存（需要外部注入或覆写）"""
        raise NotImplementedError("请通过参数注入 file_saver")
