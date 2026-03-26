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
    def list_all(cls, video_type: str = "long") -> list["ContentFolder"]:
        """Notionが設定されていればNotionから、なければローカルから読み込む。

        Args:
            video_type: "long" または "short"
        """
        from config.settings import get_settings
        settings = get_settings()

        # video_typeに対応するページIDを選択
        if video_type == "short":
            notion_page_id = settings.notion_renkau_short_page_id
        else:
            notion_page_id = settings.notion_renkau_long_page_id

        # long/short専用ページIDが設定されていればそちらを使う、なければ旧来のcontent_page_idへフォールバック
        page_id = notion_page_id or settings.notion_content_page_id

        if page_id:
            try:
                return cls._list_from_notion(
                    api_key=settings.notion_api_key.get_secret_value(),
                    parent_page_id=page_id,
                    video_type=video_type,
                )
            except Exception as e:
                logger.warning(f"Notion読み込み失敗、ローカルにフォールバック: {e}")

        return cls._list_from_local(video_type=video_type)

    @classmethod
    def _list_from_notion(cls, api_key: str, parent_page_id: str, video_type: str = "long") -> list["ContentFolder"]:
        """Notionの親ページ配下の子ページをフォルダとして返す。

        long/short専用ページが設定されている場合は、そのページ配下のコンテンツを
        単一のフォルダとしてまとめて返す（Renkauという1フォルダ）。
        """
        from notion.content_reader import NotionContentReader
        from config.settings import get_settings
        settings = get_settings()

        # long/short専用ページIDが使われている場合は単一フォルダとして扱う
        is_long_short_page = (
            parent_page_id.replace("-", "") in [
                settings.notion_renkau_long_page_id.replace("-", ""),
                settings.notion_renkau_short_page_id.replace("-", ""),
            ]
        )

        reader = NotionContentReader(api_key, parent_page_id)

        if is_long_short_page:
            # long/shortページ配下の全子ページを1フォルダのコンテキストとしてまとめる
            child_pages = reader.list_child_pages()
            parts = []
            all_keywords: list[str] = []
            for page in child_pages:
                # 「生成物」ページはスキップ
                if page["title"] == "生成物":
                    continue
                try:
                    text = reader.get_page_text(page["id"])
                    parts.append(f"## {page['title']}\n{text}")
                    all_keywords.extend(reader.get_page_keywords(text))
                except Exception as e:
                    logger.warning(f"ページ読み込み失敗 ({page['title']}): {e}")

            context = "\n\n---\n\n".join(parts)
            suffix = "（ショート）" if video_type == "short" else "（ロング）"
            folders = [cls(
                display_name=f"Renkau{suffix}",
                description="クレカなし・審査なしで家電・スマホをレンタルできるサービス",
                keywords=list(dict.fromkeys(all_keywords)),  # 重複除去
                context=context,
            )]
            logger.info(f"Notionフォルダ読み込み完了: Renkau{suffix}")
            return folders

        # 旧来の動作: 各子ページを独立したフォルダとして返す
        child_pages = reader.list_child_pages()
        folders = []
        for page in child_pages:
            try:
                text = reader.get_page_text(page["id"])
                keywords = reader.get_page_keywords(text)
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
    def _list_from_local(cls, video_type: str = "long") -> list["ContentFolder"]:
        """ローカルの content/ ディレクトリからフォルダを読み込む。

        video_typeに対応するサブディレクトリ（long/short）があればそちらを優先する。
        """
        if not CONTENT_DIR.exists():
            return []

        folders = []
        for d in sorted(CONTENT_DIR.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue

            # long/shortサブディレクトリが存在する場合はそちらを使用
            subdir = d / video_type
            target_dir = subdir if subdir.exists() else d

            config_path = target_dir / "config.json"
            config = {}
            if config_path.exists():
                config = json.loads(config_path.read_text(encoding="utf-8"))
            elif (d / "config.json").exists():
                config = json.loads((d / "config.json").read_text(encoding="utf-8"))

            parts = []
            for md_file in sorted(target_dir.glob("*.md")):
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
