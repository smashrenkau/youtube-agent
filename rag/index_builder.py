"""LlamaIndexでRAGインデックスを構築・管理するモジュール。"""
import json
import logging
import os
import time
from pathlib import Path

from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter

from rag.notion_loader import NotionLoader

logger = logging.getLogger(__name__)

METADATA_FILE = "index_metadata.json"


class IndexBuilder:
    """Notionドキュメントからベクターインデックスを構築・キャッシュ管理する。"""

    def __init__(
        self,
        notion_loader: NotionLoader,
        cache_dir: str = "rag/cache",
        refresh_hours: int = 24,
    ) -> None:
        self.notion_loader = notion_loader
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh_hours = refresh_hours
        self._index: VectorStoreIndex | None = None

    def get_index(self, force_rebuild: bool = False) -> VectorStoreIndex:
        """インデックスを取得。キャッシュが有効なら再利用、期限切れなら再構築。"""
        if self._index is not None and not force_rebuild:
            return self._index

        if not force_rebuild and self._is_cache_valid():
            logger.info("RAGキャッシュからインデックスをロード")
            self._index = self._load_from_cache()
        else:
            logger.info("Notionからインデックスを新規構築")
            self._index = self._build_index()
            self._save_to_cache(self._index)

        return self._index

    def _is_cache_valid(self) -> bool:
        metadata_path = self.cache_dir / METADATA_FILE
        if not metadata_path.exists():
            return False

        with open(metadata_path) as f:
            metadata = json.load(f)

        built_at = metadata.get("built_at", 0)
        age_hours = (time.time() - built_at) / 3600
        return age_hours < self.refresh_hours

    def _build_index(self) -> VectorStoreIndex:
        documents_data = self.notion_loader.load_documents()

        documents = [
            Document(
                text=doc["content"],
                metadata={"title": doc["title"], "url": doc["url"], "id": doc["id"]},
            )
            for doc in documents_data
        ]

        splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
        index = VectorStoreIndex.from_documents(
            documents,
            transformations=[splitter],
            show_progress=True,
        )
        logger.info(f"インデックス構築完了: {len(documents)} ドキュメント")
        return index

    def _save_to_cache(self, index: VectorStoreIndex) -> None:
        storage_dir = self.cache_dir / "storage"
        index.storage_context.persist(persist_dir=str(storage_dir))

        metadata = {"built_at": time.time(), "doc_count": len(index.docstore.docs)}
        with open(self.cache_dir / METADATA_FILE, "w") as f:
            json.dump(metadata, f)

        logger.info(f"インデックスをキャッシュに保存: {storage_dir}")

    def _load_from_cache(self) -> VectorStoreIndex:
        from llama_index.core import StorageContext, load_index_from_storage

        storage_dir = self.cache_dir / "storage"
        storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
        index = load_index_from_storage(storage_context)
        return index  # type: ignore[return-value]
