"""RAGクエリ実行モジュール。"""
import logging

from llama_index.core import VectorStoreIndex

logger = logging.getLogger(__name__)


class Retriever:
    """インデックスに対してクエリを実行し、関連ナレッジを取得する。"""

    def __init__(self, index: VectorStoreIndex, top_k: int = 5) -> None:
        self.index = index
        self.top_k = top_k
        self._retriever = index.as_retriever(similarity_top_k=top_k)

    def retrieve(self, query: str) -> str:
        """クエリに関連するナレッジをテキストとして返す。"""
        nodes = self._retriever.retrieve(query)

        if not nodes:
            logger.debug(f"クエリ '{query}' に関連するナレッジが見つかりませんでした")
            return ""

        chunks = []
        for i, node in enumerate(nodes, 1):
            title = node.metadata.get("title", "不明")
            chunks.append(f"[{i}] {title}\n{node.text}")

        result = "\n\n---\n\n".join(chunks)
        logger.debug(f"クエリ '{query}': {len(nodes)} 件のナレッジを取得")
        return result
