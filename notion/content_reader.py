"""Notionからコンテンツフォルダを読み込むモジュール。"""
import logging
import re

logger = logging.getLogger(__name__)


class NotionContentReader:
    """Notionの親ページ配下の子ページをコンテンツフォルダとして読み込む。"""

    def __init__(self, api_key: str, parent_page_id: str) -> None:
        from notion_client import Client
        self.client = Client(auth=api_key)
        self.parent_page_id = parent_page_id.replace("-", "")

    def list_child_pages(self) -> list[dict]:
        """親ページ直下の子ページ一覧を返す。[{id, title}, ...]"""
        response = self.client.blocks.children.list(block_id=self.parent_page_id)
        pages = []
        for block in response.get("results", []):
            if block["type"] == "child_page":
                pages.append({
                    "id": block["id"].replace("-", ""),
                    "title": block["child_page"]["title"],
                })
        return pages

    def get_page_text(self, page_id: str) -> str:
        """ページの全ブロックをMarkdown風テキストとして返す。
        子ページがある場合はその内容も再帰的に結合する。
        """
        # 直下ブロックを取得
        direct_text = self._read_blocks(page_id)

        # 子ページがあれば内容を結合
        child_pages = self.list_child_pages_of(page_id)
        if child_pages:
            child_parts = []
            for child in child_pages:
                child_text = self._read_blocks(child["id"])
                if child_text.strip():
                    child_parts.append(f"## {child['title']}\n{child_text}")
            return "\n\n".join(child_parts)

        return direct_text

    def list_child_pages_of(self, page_id: str) -> list[dict]:
        """指定ページ直下の子ページ一覧を返す。"""
        response = self.client.blocks.children.list(block_id=page_id)
        pages = []
        for block in response.get("results", []):
            if block["type"] == "child_page":
                pages.append({
                    "id": block["id"].replace("-", ""),
                    "title": block["child_page"]["title"],
                })
        return pages

    def _read_blocks(self, page_id: str) -> str:
        """ページのブロックをテキストとして返す（子ページは除く）。"""
        parts = []
        cursor = None

        while True:
            kwargs: dict = {"block_id": page_id}
            if cursor:
                kwargs["start_cursor"] = cursor

            response = self.client.blocks.children.list(**kwargs)

            for block in response.get("results", []):
                text = self._block_to_text(block)
                if text:
                    parts.append(text)

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        return "\n".join(parts)

    def get_page_keywords(self, page_text: str) -> list[str]:
        """ページテキストの「## キーワード」セクションからキーワードを抽出する。"""
        # 「## キーワード」「## 検索キーワード」などのセクションを探す
        match = re.search(
            r"##\s*(?:検索)?キーワード[^\n]*\n(.*?)(?=\n##|\Z)",
            page_text,
            re.DOTALL,
        )
        if not match:
            return []

        block = match.group(1)
        keywords = []
        for line in block.splitlines():
            line = line.strip().lstrip("-・ ")
            if line:
                # カンマ区切りの場合も分割
                for kw in re.split(r"[,、，]", line):
                    kw = kw.strip()
                    if kw:
                        keywords.append(kw)
        return keywords

    def _block_to_text(self, block: dict) -> str:
        btype = block["type"]
        inline_types = (
            "paragraph",
            "bulleted_list_item",
            "numbered_list_item",
            "quote",
            "callout",
            "toggle",
        )
        if btype in inline_types:
            rich_text = block[btype].get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_text)
            if not text:
                return ""
            if btype == "bulleted_list_item":
                return f"- {text}"
            if btype == "numbered_list_item":
                return f"1. {text}"
            return text

        if btype.startswith("heading_"):
            rich_text = block[btype].get("rich_text", [])
            text = "".join(rt.get("plain_text", "") for rt in rich_text)
            level = int(btype[-1])
            return f"{'#' * level} {text}"

        if btype == "divider":
            return "---"

        return ""
