# ================= 审核检查器基类 =================
"""
所有审核检查器的基类
"""
from abc import ABC, abstractmethod
from typing import Any
from ..audit_report import CheckResult


class BaseCheck(ABC):
    """审核检查器基类"""

    # 检查器名称（子类需覆盖）
    name: str = "base_check"

    @abstractmethod
    def execute(self, state: Any) -> CheckResult:
        """
        执行检查

        Args:
            state: StateManager 实例

        Returns:
            CheckResult 检查结果
        """
        pass

    def quick_check(self, content: str) -> CheckResult:
        """
        快速检查（用于单块处理时）

        Args:
            content: 要检查的内容

        Returns:
            CheckResult 检查结果（简化版）
        """
        # 默认实现：跳过快速检查
        return CheckResult(
            name=self.name,
            passed=True,
            score=1.0,
            message="快速检查未实现，默认通过"
        )
