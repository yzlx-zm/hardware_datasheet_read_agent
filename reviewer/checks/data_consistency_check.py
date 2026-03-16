# ================= 数据一致性检查 =================
"""
抽查关键数据与原文一致性
"""
import re
from typing import Dict, Set, List, Any
from .base import BaseCheck
from ..audit_report import CheckResult
from config.constants import KEY_DATA_PATTERNS


class DataConsistencyCheck(BaseCheck):
    """数据一致性检查器"""

    name = "data_consistency"
    patterns = KEY_DATA_PATTERNS

    def execute(self, state) -> CheckResult:
        """
        检查生成内容中的关键数据是否与原文一致

        Args:
            state: StateManager 实例

        Returns:
            CheckResult 包含数据不一致详情
        """
        original = state.original_text
        generated = self._merge_chapters(state.generated_chapters)

        if not original:
            return CheckResult(
                name=self.name,
                passed=True,
                score=1.0,
                message="无原文数据，跳过一致性检查",
                details={"skipped": True, "reason": "no_original_text"}
            )

        # 1. 提取原文中的关键数据
        original_data = self._extract_key_data(original)

        # 2. 提取生成内容中的关键数据
        generated_data = self._extract_key_data(generated)

        # 3. 比对一致性
        inconsistencies = []

        for key, orig_values in original_data.items():
            gen_values = generated_data.get(key, set())

            # 只检查原文中有值的情况
            if not orig_values:
                continue

            # 检查生成值中是否有原文中不存在的新值
            # （注意：生成值是原文的子集是正常的，但出现原文没有的值可能是幻觉）
            unexpected = gen_values - orig_values

            if unexpected:
                inconsistencies.append({
                    "type": key,
                    "description": f"发现原文中不存在的{self._get_type_description(key)}",
                    "expected_in_original": sorted(list(orig_values))[:10],  # 最多10个
                    "unexpected_in_generated": sorted(list(unexpected))[:10]
                })

        # 4. 反向检查：原文中有但生成内容中缺失的关键数据
        for key, orig_values in original_data.items():
            gen_values = generated_data.get(key, set())

            if orig_values and not gen_values:
                # 原文有数据但生成内容完全没有
                inconsistencies.append({
                    "type": f"{key}_missing",
                    "description": f"生成内容中缺失{self._get_type_description(key)}",
                    "original_values": sorted(list(orig_values))[:5]
                })

        # 计算得分：每个不一致项扣0.15分
        score = max(0.0, 1.0 - len(inconsistencies) * 0.15)

        return CheckResult(
            name=self.name,
            passed=len(inconsistencies) == 0,
            score=score,
            details={
                "original_data_types": list(original_data.keys()),
                "generated_data_types": list(generated_data.keys()),
                "inconsistencies_count": len(inconsistencies),
                "inconsistencies": inconsistencies
            },
            message=f"数据一致性检查完成，发现{len(inconsistencies)}处问题"
                    if inconsistencies else "关键数据与原文一致"
        )

    def _extract_key_data(self, text: str) -> Dict[str, Set[str]]:
        """
        从文本中提取关键数据

        Args:
            text: 文本内容

        Returns:
            数据类型到值集合的映射
        """
        result = {}

        for key, pattern in self.patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # 统一格式（转大写、去重）
                values = set(m.upper() if m.startswith('0x') else m for m in matches)
                result[key] = values

        return result

    def _merge_chapters(self, chapters: Dict[str, str]) -> str:
        """合并章节内容用于检查"""
        return "\n\n".join([
            f"## {name}\n{content}"
            for name, content in chapters.items()
        ])

    def _get_type_description(self, key: str) -> str:
        """获取数据类型的中文名称"""
        descriptions = {
            "baud_rate": "波特率",
            "baud_rate_alt": "波特率",
            "frame_header": "帧头",
            "register_addr": "寄存器地址",
            "data_bits": "数据位",
            "stop_bits": "停止位",
            "parity": "校验位",
            "error_code": "错误码",
            "baud_rate_missing": "波特率",
            "frame_header_missing": "帧头",
            "register_addr_missing": "寄存器地址",
            "error_code_missing": "错误码"
        }
        return descriptions.get(key, key)

    def quick_check(self, content: str) -> CheckResult:
        """
        快速检查内容中的关键数据

        Args:
            content: 单块生成的内容

        Returns:
            CheckResult
        """
        extracted = self._extract_key_data(content)

        if not extracted:
            return CheckResult(
                name=self.name,
                passed=True,
                score=1.0,
                message="当前块无关键数据",
                details={"extracted": {}}
            )

        # 简要统计
        summary = {k: len(v) for k, v in extracted.items()}

        return CheckResult(
            name=self.name,
            passed=True,
            score=1.0,
            message=f"提取到{sum(summary.values())}个关键数据点",
            details={"extracted_count": summary}
        )
