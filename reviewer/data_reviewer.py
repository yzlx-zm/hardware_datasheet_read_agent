# ================= 数据审核器 =================
"""
深度数据审核，多维度检查生成内容质量
"""
import logging
from typing import Dict, Any, Optional, List

from .audit_report import AuditReport, CheckResult
from .checks import StructureCheck, TableFormatCheck, DataConsistencyCheck


class DataReviewer:
    """
    数据审核器

    支持两个层次：
    1. quick_check() - 快速检查，用于单块处理时
    2. review() - 深度审核，用于全部生成完成后
    """

    def __init__(self, config: Optional[Dict] = None, logger: Optional[logging.Logger] = None):
        """
        初始化审核器

        Args:
            config: 配置字典，可包含审核相关配置
            logger: 日志对象
        """
        self.config = config or {}
        self.logger = logger or logging.getLogger(__name__)

        # 初始化检查器
        review_config = self.config.get('review', {})
        checks_config = review_config.get('checks', {})

        self.checks = []

        if checks_config.get('structure', True):
            self.checks.append(StructureCheck())

        if checks_config.get('table_format', True):
            self.checks.append(TableFormatCheck())

        if checks_config.get('data_consistency', True):
            self.checks.append(DataConsistencyCheck())

    def review(self, state) -> AuditReport:
        """
        执行全面深度审核

        Args:
            state: StateManager 实例，包含原文和生成内容

        Returns:
            AuditReport 审核报告
        """
        self.logger.info(f"开始深度审核，共{len(self.checks)}个检查项...")

        report = AuditReport()

        for check in self.checks:
            try:
                self.logger.debug(f"执行检查: {check.name}")
                result = check.execute(state)
                report.add_check_result(result)

                # 收集问题摘要
                if check.name == "structure":
                    details = result.details
                    report.missing_chapters = details.get("missing", [])
                    report.empty_chapters = details.get("empty", [])

                elif check.name == "table_format":
                    report.table_issues = result.details.get("issues", [])

                elif check.name == "data_consistency":
                    report.data_inconsistencies = result.details.get("inconsistencies", [])

                status = "✅" if result.passed else "❌"
                self.logger.info(f"  {status} {check.name}: {result.message}")

            except Exception as e:
                self.logger.error(f"检查 {check.name} 执行失败: {str(e)}")
                # 添加失败的检查结果
                report.add_check_result(CheckResult(
                    name=check.name,
                    passed=False,
                    score=0.0,
                    message=f"检查执行失败: {str(e)}",
                    details={"error": str(e)}
                ))

        self.logger.info(f"审核完成: 得分={report.overall_score:.1%}, 通过={report.passed}")

        return report

    def quick_check(self, content: str) -> List[CheckResult]:
        """
        快速检查（用于单块处理时）

        Args:
            content: 单块生成的内容

        Returns:
            List[CheckResult] 各检查项的快速检查结果
        """
        results = []

        for check in self.checks:
            try:
                result = check.quick_check(content)
                results.append(result)
            except Exception as e:
                self.logger.warning(f"快速检查 {check.name} 失败: {str(e)}")

        return results

    def should_retry(self, report: AuditReport) -> bool:
        """
        判断是否应该重试

        Args:
            report: 审核报告

        Returns:
            bool 是否应该重试
        """
        review_config = self.config.get('review', {})
        strict_mode = review_config.get('strict_mode', False)

        # 严格模式下，任何失败都不重试，直接终止
        if strict_mode and not report.passed:
            return False

        # 判断是否可重试
        return report.can_retry

    def get_retry_feedback(self, report: AuditReport) -> str:
        """
        生成重试反馈（用于追加到Prompt）

        Args:
            report: 审核报告

        Returns:
            str 反馈文本
        """
        feedback_parts = ["【上次生成的问题，请修正】"]

        if report.missing_chapters:
            feedback_parts.append(f"- 缺失章节：{', '.join(report.missing_chapters)}")

        if report.empty_chapters:
            feedback_parts.append(f"- 空章节：{', '.join(report.empty_chapters)}")

        if report.table_issues:
            feedback_parts.append(f"- 表格问题（共{len(report.table_issues)}个）：")
            for issue in report.table_issues[:3]:  # 最多3个
                feedback_parts.append(f"  - {issue.get('description', str(issue))}")

        if report.data_inconsistencies:
            feedback_parts.append(f"- 数据不一致（共{len(report.data_inconsistencies)}处）：")
            for issue in report.data_inconsistencies[:3]:
                feedback_parts.append(f"  - {issue.get('description', str(issue))}")

        return "\n".join(feedback_parts)
