"""Notion APIからナレッジを取得するモジュール。"""
import logging
from notion_client import Client

logger = logging.getLogger(__name__)

# ナレッジとして読み込まない子ページのタイトル
EXCLUDED_PAGES = {"生成物", "スライド仕様書"}


class NotionLoader:
    """Notionの指定ページ配下の子ページからナレッジを取得する。"""

    def __init__(self, api_key: str, knowledge_page_id: str) -> None:
        self.client = Client(auth=api_key)
        self.knowledge_page_id = knowledge_page_id

    def load_documents(self) -> list[dict[str, str]]:
        """知識ページ配下の子ページをドキュメントリストとして返す。"""
        child_pages = self._get_child_pages(self.knowledge_page_id)
        documents = []

        for page_id, title in child_pages:
            if title in EXCLUDED_PAGES:
                logger.debug(f"スキップ: {title}")
                continue
            try:
                content = self.get_page_content(page_id)
                documents.append({
                    "id": page_id,
                    "title": title,
                    "content": f"# {title}\n\n{content}",
                    "url": f"https://www.notion.so/{page_id.replace('-', '')}",
                })
                logger.debug(f"ページロード完了: {title}")
            except Exception as e:
                logger.warning(f"ページ取得失敗 ({title}): {e}")

        logger.info(f"Notion: {len(documents)} ページ取得完了")
        return documents

    def _get_child_pages(self, page_id: str) -> list[tuple[str, str]]:
        """指定ページの子ページを(page_id, title)のリストで返す。"""
        results = []
        cursor = None

        while True:
            kwargs: dict = {"block_id": page_id}
            if cursor:
                kwargs["start_cursor"] = cursor

            response = self.client.blocks.children.list(**kwargs)
            for block in response.get("results", []):
                if block["type"] == "child_page":
                    results.append((
                        block["id"],
                        block["child_page"]["title"],
                    ))

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return results

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

            children = block.get("children", [])
            if children:
                lines.append(self._blocks_to_text(children, indent + 1))

        return "\n".join(lines)
