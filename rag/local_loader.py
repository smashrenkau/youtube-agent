"""ローカルMDファイルからナレッジを取得するモジュール。"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalLoader:
    """content/ ディレクトリのMDファイルからナレッジを取得する。"""

    def __init__(self, content_dir: str = "content") -> None:
        self.content_dir = Path(content_dir)

    def load_documents(self) -> list[dict[str, str]]:
        """content/以下のMDファイルをドキュメントリストとして返す。"""
        if not self.content_dir.exists():
            logger.warning(f"content/ディレクトリが見つかりません: {self.content_dir}")
            return []

        documents = []
        for md_file in sorted(self.content_dir.rglob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem.replace("_", " ").title()
                relative = md_file.relative_to(self.content_dir)
                doc_id = str(relative).replace("/", "_").replace("\\", "_")
                documents.append({
                    "id": doc_id,
                    "title": title,
                    "content": f"# {title}\n\n{content}",
                    "url": str(md_file.absolute()),
                })
                logger.debug(f"ファイル読み込み完了: {relative}")
            except Exception as e:
                logger.warning(f"ファイル読み込み失敗 ({md_file}): {e}")

        logger.info(f"ローカル: {len(documents)} ファイル取得完了")
        return documents
