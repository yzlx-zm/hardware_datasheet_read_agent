# ================= 审核报告 =================
"""
审核报告数据结构和生成器
"""
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class CheckResult:
    """单个检查项的结果"""
    name: str                          # 检查项名称
    passed: bool                       # 是否通过
    score: float                       # 得分 (0.0 - 1.0)
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息
    message: str = ""                  # 简要说明

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditReport:
    """
    审核报告

    包含所有检查项的结果和总体评估
    """
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    check_results: List[CheckResult] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False
    can_retry: bool = True

    # 问题摘要
    missing_chapters: List[str] = field(default_factory=list)
    empty_chapters: List[str] = field(default_factory=list)
    table_issues: List[Dict] = field(default_factory=list)
    data_inconsistencies: List[Dict] = field(default_factory=list)

    def add_check_result(self, result: CheckResult) -> None:
        """添加检查结果"""
        self.check_results.append(result)
        self._recalculate_score()

    def _recalculate_score(self) -> None:
        """重新计算总分"""
        if not self.check_results:
            self.overall_score = 0.0
            return

        # 加权平均：数据一致性权重更高
        weights = {
            "structure": 0.3,
            "table_format": 0.2,
            "data_consistency": 0.5
        }

        total_weight = 0.0
        weighted_score = 0.0

        for result in self.check_results:
            weight = weights.get(result.name, 0.33)
            weighted_score += result.score * weight
            total_weight += weight

        self.overall_score = weighted_score / total_weight if total_weight > 0 else 0.0

        # 判断是否通过：总体得分 >= 0.7 且所有关键检查通过
        critical_passed = all(
            r.passed for r in self.check_results
            if r.name in ["structure", "data_consistency"]
        )
        self.passed = self.overall_score >= 0.7 and critical_passed

        # 判断是否可重试：有可修复的问题
        self.can_retry = (
            not self.passed and
            self.overall_score >= 0.4 and  # 得分不能太低
            len(self.missing_chapters) <= 2  # 缺失章节不能太多
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 3),
            "passed": self.passed,
            "can_retry": self.can_retry,
            "check_results": [r.to_dict() for r in self.check_results],
            "summary": {
                "missing_chapters": self.missing_chapters,
                "empty_chapters": self.empty_chapters,
                "table_issues_count": len(self.table_issues),
                "data_inconsistencies_count": len(self.data_inconsistencies)
            },
            "issues": {
                "table_issues": self.table_issues[:10],  # 最多显示10个
                "data_inconsistencies": self.data_inconsistencies[:10]
            }
        }

    def to_json(self, indent: int = 2) -> str:
        """生成 JSON 格式报告"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        """生成 Markdown 格式报告"""
        lines = [
            "# 审核报告",
            "",
            f"**生成时间**: {self.timestamp}",
            f"**总体得分**: {self.overall_score:.1%}",
            f"**审核结果**: {'✅ 通过' if self.passed else '❌ 未通过'}",
            f"**可重试**: {'是' if self.can_retry else '否'}",
            "",
            "## 检查项详情",
            ""
        ]

        # 检查项表格
        lines.extend([
            "| 检查项 | 状态 | 得分 | 说明 |",
            "|--------|------|------|------|"
        ])

        for result in self.check_results:
            status = "✅" if result.passed else "❌"
            lines.append(
                f"| {result.name} | {status} | {result.score:.1%} | {result.message} |"
            )

        lines.append("")

        # 问题详情
        if self.missing_chapters:
            lines.extend([
                "## 缺失章节",
                "",
                *[f"- {ch}" for ch in self.missing_chapters],
                ""
            ])

        if self.empty_chapters:
            lines.extend([
                "## 空章节",
                "",
                *[f"- {ch}" for ch in self.empty_chapters],
                ""
            ])

        if self.table_issues:
            lines.extend([
                "## 表格问题",
                "",
                *[f"- {issue.get('description', str(issue))}" for issue in self.table_issues[:5]],
                ""
            ])

        if self.data_inconsistencies:
            lines.extend([
                "## 数据不一致",
                "",
                *[f"- {issue.get('type', '未知')}: {issue.get('description', str(issue))}"
                  for issue in self.data_inconsistencies[:5]],
                ""
            ])

        return "\n".join(lines)

    def get_summary(self) -> str:
        """获取简要摘要"""
        issues = []
        if self.missing_chapters:
            issues.append(f"缺失{len(self.missing_chapters)}个章节")
        if self.table_issues:
            issues.append(f"{len(self.table_issues)}个表格问题")
        if self.data_inconsistencies:
            issues.append(f"{len(self.data_inconsistencies)}处数据不一致")

        if self.passed:
            return "审核通过"
        elif issues:
            return f"审核未通过：{', '.join(issues)}"
        else:
            return f"审核未通过（得分: {self.overall_score:.1%}）"
