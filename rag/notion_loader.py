"""Notion APIからナレッジを取得するモジュール。"""
import logging
from notion_client import Client

logger = logging.getLogger(__name__)


class NotionLoader:
    """Notion APIからページとブロックを再帰的に取得する。"""

    def __init__(self, api_key: str, database_id: str) -> None:
        self.client = Client(auth=api_key)
        self.database_id = database_id

    def load_all_pages(self) -> list[dict]:
        """データベース内の全ページをロード。"""
        pages = []
        cursor = None

        while True:
            kwargs: dict = {"database_id": self.database_id}
            if cursor:
                kwargs["start_cursor"] = cursor

            response = self.client.databases.query(**kwargs)
            pages.extend(response["results"])

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        logger.info(f"Notion: {len(pages)} ページ取得完了")
        return pages

    def get_page_content(self, page_id: str) -> str:
        """ページの全テキストコンテンツを再帰的に取得。"""
        blocks = self._get_blocks(page_id)
        return self._blocks_to_text(blocks)

    def _get_blocks(self, block_id: str) -> list[dict]:
        """ブロックを再帰的に取得。"""
        blocks = []
        cursor = None

        while True:
            kwargs: dict = {"block_id": block_id}
            if cursor:
                kwargs["start_cursor"] = cursor

            response = self.client.blocks.children.list(**kwargs)
            for block in response["results"]:
                blocks.append(block)
                if block.get("has_children"):
                    block["children"] = self._get_blocks(block["id"])

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return blocks

    def _blocks_to_text(self, blocks: list[dict], indent: int = 0) -> str:
        """ブロックリストをプレーンテキストに変換。"""
        lines = []
        prefix = "  " * indent

        for block in blocks:
            block_type = block["type"]
            rich_texts = block.get(block_type, {}).get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_texts)

            if text:
                lines.append(f"{prefix}{text}")

            # 子ブロックを再帰処理
            children = block.get("children", [])
            if children:
                lines.append(self._blocks_to_text(children, indent + 1))

        return "\n".join(lines)

    def load_documents(self) -> list[dict[str, str]]:
        """全ページのコンテンツをドキュメントリストとして返す。"""
        pages = self.load_all_pages()
        documents = []

        for page in pages:
            page_id = page["id"]
            # タイトルプロパティを取得
            title = ""
            for prop in page.get("properties", {}).values():
                if prop["type"] == "title":
                    title = "".join(
                        rt["plain_text"] for rt in prop.get("title", [])
                    )
                    break

            try:
                content = self.get_page_content(page_id)
                documents.append({
                    "id": page_id,
                    "title": title,
                    "content": f"# {title}\n\n{content}",
                    "url": page.get("url", ""),
                })
                logger.debug(f"  ページロード完了: {title}")
            except Exception as e:
                logger.warning(f"  ページ取得失敗 ({page_id}): {e}")

        return documents
