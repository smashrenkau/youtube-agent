"""生成物をNotionに自動保存するモジュール。"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

STORAGE_PAGE_NAME = "生成物"


class NotionStorage:
    """タイトル・台本・スライドをNotionに自動保存する。"""

    def __init__(self, api_key: str, renkau_page_id: str, parent_page_id: str = "") -> None:
        """
        Args:
            api_key: Notion APIキー
            renkau_page_id: Renkauルートページ（フォールバック用）
            parent_page_id: 生成物の保存先親ページ（long/short動画ページ）。
                            指定した場合はこのページ配下に「生成物」を探す/作る。
        """
        from notion_client import Client
        self.client = Client(auth=api_key)
        # parent_page_idが指定されていればそちらを優先
        self.renkau_page_id = (parent_page_id or renkau_page_id).replace("-", "")
        self._storage_page_id: str | None = None

    # ──────────────────────────────────────────
    # 内部：生成物ページIDの取得
    # ──────────────────────────────────────────

    def _get_storage_page_id(self) -> str:
        """「生成物」ページのIDを返す（なければ作成）。"""
        if self._storage_page_id:
            return self._storage_page_id

        response = self.client.blocks.children.list(block_id=self.renkau_page_id)
        for block in response.get("results", []):
            if block["type"] == "child_page":
                if block["child_page"]["title"] == STORAGE_PAGE_NAME:
                    self._storage_page_id = block["id"].replace("-", "")
                    return self._storage_page_id

        # 見つからなければ作成
        page = self.client.pages.create(
            parent={"type": "page_id", "page_id": self.renkau_page_id},
            properties={"title": {"title": [self._text("生成物")]}},
            children=[{"object": "block", "type": "paragraph",
                        "paragraph": {"rich_text": [self._text("タイトル・台本・スライドが自動保存されます。")]}}]
        )
        self._storage_page_id = page["id"].replace("-", "")
        logger.info(f"「生成物」ページを作成: {self._storage_page_id}")
        return self._storage_page_id

    # ──────────────────────────────────────────
    # 既存タイトル一覧
    # ──────────────────────────────────────────

    def get_existing_titles(self) -> list[str]:
        """生成物フォルダ内の既存タイトル一覧を返す。"""
        storage_id = self._get_storage_page_id()
        response = self.client.blocks.children.list(block_id=storage_id)
        titles = []
        for block in response.get("results", []):
            if block["type"] == "child_page":
                titles.append(block["child_page"]["title"])
        return titles

    # ──────────────────────────────────────────
    # タイトル保存
    # ──────────────────────────────────────────

    def save_title(self, title: str) -> str:
        """タイトルフォルダを作成してpage_idを返す。"""
        storage_id = self._get_storage_page_id()
        now = datetime.now().strftime("%Y/%m/%d %H:%M")
        page = self.client.pages.create(
            parent={"type": "page_id", "page_id": storage_id},
            properties={"title": {"title": [self._text(title)]}},
            children=[
                {"object": "block", "type": "paragraph",
                 "paragraph": {"rich_text": [self._text(f"生成日時: {now}")]}}
            ]
        )
        page_id = page["id"].replace("-", "")
        logger.info(f"タイトルページ作成: {title}")
        return page_id

    # ──────────────────────────────────────────
    # 台本保存
    # ──────────────────────────────────────────

    def save_script(self, title_page_id: str, script: str) -> None:
        """台本をタイトルページ直下に保存する。"""
        # 台本ページを作成
        script_page = self.client.pages.create(
            parent={"type": "page_id", "page_id": title_page_id},
            properties={"title": {"title": [self._text("台本")]}},
            children=[]
        )
        script_page_id = script_page["id"].replace("-", "")

        # 台本テキストをブロックに分割して追加（Notion APIは1回100ブロックまで）
        blocks = self._script_to_blocks(script)
        for i in range(0, len(blocks), 95):
            self.client.blocks.children.append(
                block_id=script_page_id,
                children=blocks[i:i + 95]
            )

        logger.info(f"台本を保存: {len(script)}文字")

    # ──────────────────────────────────────────
    # 参照動画保存
    # ──────────────────────────────────────────

    def save_reference_videos(self, title_page_id: str, videos: list[dict]) -> None:
        """参照したYouTube動画リストをタイトルページ直下に保存する。"""
        blocks: list[dict] = [
            {"object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [self._text("参照した高再生数YouTube動画")]}}
        ]
        for v in videos:
            view = f"{v['view_count']:,}" if isinstance(v.get("view_count"), int) else "-"
            label = f"{v['title']} ({v['channel']} / {view}回再生)"
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": label, "link": {"url": v["url"]}},
                    }]
                },
            })

        ref_page = self.client.pages.create(
            parent={"type": "page_id", "page_id": title_page_id},
            properties={"title": {"title": [self._text("参照動画")]}},
            children=blocks,
        )
        logger.info(f"参照動画ページ作成: {len(videos)}件")

    # ──────────────────────────────────────────
    # スライド保存
    # ──────────────────────────────────────────

    def save_slides(self, title_page_id: str, slides: list[dict]) -> None:
        """スライド情報をタイトルページ直下に保存する。"""
        slide_page = self.client.pages.create(
            parent={"type": "page_id", "page_id": title_page_id},
            properties={"title": {"title": [self._text("スライド")]}},
            children=[]
        )
        slide_page_id = slide_page["id"].replace("-", "")

        blocks = [
            {"object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [self._text(f"スライド枚数: {len(slides)}枚")]}}
        ]
        for slide in slides:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [self._text(f"スライド{slide['slide_num']}: {slide['title']}")]
                }
            })

        self.client.blocks.children.append(block_id=slide_page_id, children=blocks)
        logger.info(f"スライド情報を保存: {len(slides)}枚")

    # ──────────────────────────────────────────
    # ユーティリティ
    # ──────────────────────────────────────────

    def _text(self, content: str) -> dict:
        return {"type": "text", "text": {"content": content[:2000]}}

    def _script_to_blocks(self, script: str) -> list[dict]:
        """台本テキストを段落ブロックのリストに変換する。"""
        blocks = []
        for line in script.splitlines():
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [self._text(line)] if line.strip() else []}
            })
        return blocks
