# ================= 状态管理器 =================
"""
管理整个处理过程中的数据状态，确保原文可追溯，支持审核比对
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class LLMInteraction:
    """LLM 交互记录"""
    chunk_index: int
    prompt: str
    response: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    token_usage: Optional[Dict] = None
    duration_seconds: Optional[float] = None


@dataclass
class ChunkInfo:
    """分块信息"""
    index: int
    content: str
    token_count: int
    source_pages: Optional[List[int]] = None


class StateManager:
    """
    状态管理器：存储和处理过程中的所有数据状态

    核心职责：
    1. 保存原始文档文本（防止丢失，用于审核）
    2. 管理分块信息
    3. 存储生成的章节内容
    4. 记录 LLM 交互历史（可追溯）
    """

    def __init__(self):
        self.original_text: str = ""
        self.original_file_path: str = ""
        self.chunks: List[ChunkInfo] = []
        self.generated_chapters: Dict[str, str] = {}
        self.llm_interactions: List[LLMInteraction] = []
        self.audit_result: Optional[Any] = None
        self.metadata: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    def store_original(self, text: str, file_path: str = "") -> None:
        """
        存储原始文档文本

        Args:
            text: 原始文档完整文本
            file_path: 文档文件路径（用于记录）
        """
        self.original_text = text
        self.original_file_path = file_path
        self._update_timestamp()

    def add_chunk(self, content: str, token_count: int, index: Optional[int] = None) -> None:
        """
        添加分块信息

        Args:
            content: 分块内容
            token_count: token 数量
            index: 分块索引（默认自动递增）
        """
        if index is None:
            index = len(self.chunks)
        chunk = ChunkInfo(
            index=index,
            content=content,
            token_count=token_count
        )
        self.chunks.append(chunk)
        self._update_timestamp()

    def set_chunks(self, chunks: List[str], token_counts: Optional[List[int]] = None) -> None:
        """
        批量设置分块

        Args:
            chunks: 分块内容列表
            token_counts: token 数量列表（可选，会自动计算）
        """
        self.chunks = []
        for i, chunk in enumerate(chunks):
            token_count = token_counts[i] if token_counts else len(chunk) // 3
            self.add_chunk(chunk, token_count, i)
        self._update_timestamp()

    def store_chapter(self, chapter_name: str, content: str) -> None:
        """
        存储生成的章节内容

        Args:
            chapter_name: 章节名称
            content: 章节内容
        """
        self.generated_chapters[chapter_name] = content
        self._update_timestamp()

    def merge_chapters(self, chapters: Dict[str, str]) -> None:
        """
        批量合并章节内容

        Args:
            chapters: 章节名称到内容的映射
        """
        for name, content in chapters.items():
            if name in self.generated_chapters:
                # 逐行去重合并
                existing = self.generated_chapters[name]
                for line in content.split('\n'):
                    if line.strip() and line.strip() not in existing:
                        existing += "\n" + line
                self.generated_chapters[name] = existing.strip()
            else:
                self.generated_chapters[name] = content
        self._update_timestamp()

    def log_llm_interaction(
        self,
        chunk_index: int,
        prompt: str,
        response: str,
        token_usage: Optional[Dict] = None,
        duration: Optional[float] = None
    ) -> None:
        """
        记录 LLM 交互

        Args:
            chunk_index: 对应的分块索引
            prompt: 发送的 Prompt
            response: LLM 返回的响应
            token_usage: token 使用情况
            duration: 交互耗时（秒）
        """
        interaction = LLMInteraction(
            chunk_index=chunk_index,
            prompt=prompt,
            response=response,
            token_usage=token_usage,
            duration_seconds=duration
        )
        self.llm_interactions.append(interaction)
        self._update_timestamp()

    def get_chunk_context(self, chunk_index: int, context_range: int = 1) -> Dict[str, str]:
        """
        获取分块的上下文信息

        Args:
            chunk_index: 目标分块索引
            context_range: 前后文范围（块数）

        Returns:
            包含 prev_chunks, current_chunk, next_chunks 的字典
        """
        prev_chunks = []
        next_chunks = []

        for i in range(max(0, chunk_index - context_range), chunk_index):
            prev_chunks.append(self.chunks[i].content[:500])  # 只取前500字符

        for i in range(chunk_index + 1, min(len(self.chunks), chunk_index + context_range + 1)):
            next_chunks.append(self.chunks[i].content[:500])

        return {
            "prev_chunks": prev_chunks,
            "current_chunk": self.chunks[chunk_index].content if chunk_index < len(self.chunks) else "",
            "next_chunks": next_chunks
        }

    def get_generated_content(self) -> str:
        """获取合并后的完整生成内容"""
        return "\n\n".join([
            f"## {name}\n{content}"
            for name, content in self.generated_chapters.items()
        ])

    def to_dict(self) -> Dict[str, Any]:
        """导出状态为字典（用于序列化）"""
        return {
            "original_file_path": self.original_file_path,
            "original_text_length": len(self.original_text),
            "chunks_count": len(self.chunks),
            "chunks": [
                {
                    "index": c.index,
                    "token_count": c.token_count,
                    "content_length": len(c.content)
                }
                for c in self.chunks
            ],
            "generated_chapters": list(self.generated_chapters.keys()),
            "llm_interactions_count": len(self.llm_interactions),
            "metadata": self.metadata
        }

    def export_full_state(self, include_content: bool = False) -> Dict[str, Any]:
        """
        导出完整状态（用于调试/审核）

        Args:
            include_content: 是否包含完整内容（可能很大）
        """
        state = self.to_dict()
        if include_content:
            state["original_text"] = self.original_text
            state["chunks_full"] = [asdict(c) for c in self.chunks]
            state["generated_chapters_full"] = self.generated_chapters
            state["llm_interactions"] = [asdict(i) for i in self.llm_interactions]
        return state

    def _update_timestamp(self) -> None:
        """更新时间戳"""
        self.metadata["updated_at"] = datetime.now().isoformat()
