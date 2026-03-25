"""コンテンツフォルダの管理クラス。NotionまたはローカルMDから読み込む。"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONTENT_DIR = Path(__file__).parent.parent / "content"


class ContentFolder:
    """ブランド・商材ごとのコンテンツフォルダ。"""

    def __init__(
        self,
        display_name: str,
        description: str = "",
        keywords: list[str] | None = None,
        context: str = "",
    ) -> None:
        self.display_name = display_name
        self.description = description
        self.keywords = keywords or []
        self._context = context

    def get_context(self) -> str:
        return self._context

    # ──────────────────────────────────────────
    # ファクトリメソッド
    # ──────────────────────────────────────────

    @classmethod
    def list_all(cls) -> list["ContentFolder"]:
        """Notionが設定されていればNotionから、なければローカルから読み込む。"""
        from config.settings import get_settings
        settings = get_settings()

        if settings.notion_content_page_id:
            try:
                return cls._list_from_notion(
                    api_key=settings.notion_api_key.get_secret_value(),
                    parent_page_id=settings.notion_content_page_id,
                )
            except Exception as e:
                logger.warning(f"Notion読み込み失敗、ローカルにフォールバック: {e}")

        return cls._list_from_local()

    @classmethod
    def _list_from_notion(cls, api_key: str, parent_page_id: str) -> list["ContentFolder"]:
        """Notionの親ページ配下の子ページをフォルダとして返す。"""
        from notion.content_reader import NotionContentReader
        reader = NotionContentReader(api_key, parent_page_id)
        child_pages = reader.list_child_pages()

        folders = []
        for page in child_pages:
            try:
                text = reader.get_page_text(page["id"])
                keywords = reader.get_page_keywords(text)
                # 先頭行をdescriptionとして使う
                first_line = next((l for l in text.splitlines() if l.strip() and not l.startswith("#")), "")
                folders.append(cls(
                    display_name=page["title"],
                    description=first_line[:80],
                    keywords=keywords,
                    context=text,
                ))
                logger.info(f"Notionフォルダ読み込み完了: {page['title']}")
            except Exception as e:
                logger.warning(f"フォルダ読み込み失敗 ({page['title']}): {e}")

        return folders

    @classmethod
    def _list_from_local(cls) -> list["ContentFolder"]:
        """ローカルの content/ ディレクトリからフォルダを読み込む。"""
        if not CONTENT_DIR.exists():
            return []

        folders = []
        for d in sorted(CONTENT_DIR.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue

            config_path = d / "config.json"
            config = {}
            if config_path.exists():
                config = json.loads(config_path.read_text(encoding="utf-8"))

            parts = []
            for md_file in sorted(d.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                section_name = md_file.stem.replace("_", " ").title()
                parts.append(f"## {section_name}\n{content}")
            context = "\n\n---\n\n".join(parts)

            folders.append(cls(
                display_name=config.get("display_name", d.name),
                description=config.get("description", ""),
                keywords=config.get("keywords", []),
                context=context,
            ))

        return folders
