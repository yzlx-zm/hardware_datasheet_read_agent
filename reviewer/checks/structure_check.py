# ================= 结构完整性检查 =================
"""
检查9章节是否完整、非空
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .base import BaseCheck
from ..audit_report import CheckResult
from config.constants import ARCHIVE_CHAPTERS, CHAPTER_PREFIX


class StructureCheck(BaseCheck):
    """结构完整性检查器"""

    name = "structure"
    required_chapters = ARCHIVE_CHAPTERS

    def execute(self, state) -> CheckResult:
        """
        检查章节结构完整性

        Args:
            state: StateManager 实例

        Returns:
            CheckResult 包含缺失和空章节信息
        """
        missing_chapters = []
        empty_chapters = []
        present_chapters = []

        generated = state.generated_chapters

        for chapter in self.required_chapters:
            if chapter not in generated:
                missing_chapters.append(chapter)
            elif not generated[chapter] or not generated[chapter].strip():
                empty_chapters.append(chapter)
            else:
                present_chapters.append(chapter)

        # 计算得分：每缺失/空一个章节扣分
        total = len(self.required_chapters)
        present_count = len(present_chapters)
        score = present_count / total if total > 0 else 0.0

        # 构建详细信息
        details = {
            "total_chapters": total,
            "present_count": present_count,
            "missing": missing_chapters,
            "empty": empty_chapters,
            "present": present_chapters
        }

        # 构建消息
        if not missing_chapters and not empty_chapters:
            message = f"全部{total}个章节完整"
        else:
            issues = []
            if missing_chapters:
                issues.append(f"缺失{len(missing_chapters)}个")
            if empty_chapters:
                issues.append(f"{len(empty_chapters)}个为空")
            message = f"章节问题：{', '.join(issues)}"

        return CheckResult(
            name=self.name,
            passed=len(missing_chapters) == 0 and len(empty_chapters) == 0,
            score=score,
            details=details,
            message=message
        )

    def quick_check(self, content: str) -> CheckResult:
        """
        快速检查内容中是否有章节标题

        Args:
            content: 单块生成的内容

        Returns:
            CheckResult
        """
        found_chapters = []

        for chapter in self.required_chapters:
            if f"{CHAPTER_PREFIX}{chapter}" in content:
                found_chapters.append(chapter)

        if not found_chapters:
            return CheckResult(
                name=self.name,
                passed=True,  # 单块可能没有章节，不视为错误
                score=1.0,
                message="当前块无章节标题（正常）",
                details={"found_chapters": []}
            )

        return CheckResult(
            name=self.name,
            passed=True,
            score=1.0,
            message=f"发现{len(found_chapters)}个章节",
            details={"found_chapters": found_chapters}
        )
