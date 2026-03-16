# ================= 表格格式检查 =================
"""
检查Markdown表格语法正确性
"""
import re
from typing import List, Dict, Tuple
from .base import BaseCheck
from ..audit_report import CheckResult
from config.constants import TABLE_CHAPTERS


class TableFormatCheck(BaseCheck):
    """表格格式检查器"""

    name = "table_format"
    table_chapters = TABLE_CHAPTERS

    def execute(self, state) -> CheckResult:
        """
        检查表格章节的Markdown表格格式

        Args:
            state: StateManager 实例

        Returns:
            CheckResult 包含所有表格问题
        """
        all_issues = []
        checked_chapters = []

        for chapter_name in self.table_chapters:
            content = state.generated_chapters.get(chapter_name, "")
            if not content.strip():
                continue

            checked_chapters.append(chapter_name)
            issues = self._check_table_syntax(content, chapter_name)
            all_issues.extend(issues)

        # 计算得分：每个问题扣0.1分
        score = max(0.0, 1.0 - len(all_issues) * 0.1)

        return CheckResult(
            name=self.name,
            passed=len(all_issues) == 0,
            score=score,
            details={
                "checked_chapters": checked_chapters,
                "issues_count": len(all_issues),
                "issues": all_issues[:20]  # 最多返回20个问题
            },
            message=f"检查{len(checked_chapters)}个表格章节，发现{len(all_issues)}个问题"
                    if all_issues else f"检查{len(checked_chapters)}个表格章节，格式正确"
        )

    def _check_table_syntax(self, content: str, chapter: str) -> List[Dict]:
        """
        检查Markdown表格语法

        检查项：
        1. 表格行是否以|开头和结尾
        2. 分隔行格式是否正确（---|---）
        3. 列数是否一致

        Args:
            content: 章节内容
            chapter: 章节名称

        Returns:
            问题列表
        """
        issues = []
        lines = content.split('\n')
        table_lines = []
        in_table = False
        table_start_line = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # 检测表格开始
            if stripped.startswith('|') and stripped.endswith('|'):
                if not in_table:
                    in_table = True
                    table_start_line = i + 1  # 1-based行号
                table_lines.append({
                    "line_num": i + 1,
                    "content": stripped,
                    "cells": self._parse_table_row(stripped)
                })
            elif in_table and not stripped:
                # 空行可能表示表格结束，但不一定
                pass
            elif in_table and not stripped.startswith('|'):
                # 确定表格结束
                if len(table_lines) >= 2:
                    issues.extend(self._validate_table(table_lines, chapter, table_start_line))
                table_lines = []
                in_table = False

        # 处理文档末尾的表格
        if in_table and len(table_lines) >= 2:
            issues.extend(self._validate_table(table_lines, chapter, table_start_line))

        return issues

    def _parse_table_row(self, line: str) -> List[str]:
        """解析表格行为单元格列表"""
        # 去掉首尾的|，按|拆分
        return [cell.strip() for cell in line[1:-1].split('|')]

    def _validate_table(self, table_lines: List[Dict], chapter: str, start_line: int) -> List[Dict]:
        """
        验证表格格式

        Args:
            table_lines: 表格行列表
            chapter: 章节名
            start_line: 起始行号

        Returns:
            问题列表
        """
        issues = []

        if len(table_lines) < 2:
            return [{
                "chapter": chapter,
                "line": start_line,
                "type": "incomplete_table",
                "description": "表格不完整（少于2行）"
            }]

        # 检查分隔行（第二行）
        separator = table_lines[1]
        sep_cells = separator["cells"]

        # 分隔行应该全是---或类似格式
        is_separator = all(
            re.match(r'^[-:]+$', cell) for cell in sep_cells if cell
        )

        if not is_separator:
            issues.append({
                "chapter": chapter,
                "line": separator["line_num"],
                "type": "invalid_separator",
                "description": f"表格分隔行格式错误：{separator['content'][:50]}"
            })

        # 检查列数一致性
        if len(table_lines) >= 2:
            header_cols = len(table_lines[0]["cells"])
            for row in table_lines[2:]:  # 跳过表头和分隔行
                row_cols = len(row["cells"])
                if row_cols != header_cols:
                    issues.append({
                        "chapter": chapter,
                        "line": row["line_num"],
                        "type": "column_mismatch",
                        "description": f"列数不一致（表头{header_cols}列，当前{row_cols}列）"
                    })
                    break  # 只报告一次

        return issues

    def quick_check(self, content: str) -> CheckResult:
        """
        快速检查内容中的表格格式

        Args:
            content: 单块生成的内容

        Returns:
            CheckResult
        """
        # 统计表格行数
        table_rows = 0
        lines = content.split('\n')

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|') and stripped.endswith('|'):
                table_rows += 1

        if table_rows == 0:
            return CheckResult(
                name=self.name,
                passed=True,
                score=1.0,
                message="当前块无表格",
                details={"table_rows": 0}
            )

        # 快速检查：表格行是否以|结尾
        issues = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('|') and not stripped.endswith('|'):
                issues.append(f"行{i+1}：表格行未以|结尾")

        return CheckResult(
            name=self.name,
            passed=len(issues) == 0,
            score=max(0.5, 1.0 - len(issues) * 0.1),
            message=f"发现{table_rows}行表格，{len(issues)}个格式问题",
            details={"table_rows": table_rows, "issues": issues[:5]}
        )
