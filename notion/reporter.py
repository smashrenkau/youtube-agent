"""パイプライン結果をNotionに自動保存するモジュール。"""
import logging
from datetime import datetime, timezone

from notion_client import Client

from models.schemas import ScriptResult, ThemeResult, UploadResult, VideoResult

logger = logging.getLogger(__name__)

# Notionブロック生成ヘルパー
def _h2(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _h3(text: str) -> dict:
    return {"object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _para(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}}

def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}}

def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}

def _code(text: str) -> dict:
    return {"object": "block", "type": "code",
            "code": {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
                     "language": "plain text"}}


class NotionReporter:
    """パイプラインの各ステップ結果をNotionの制作ログDBに保存する。"""

    def __init__(self, api_key: str, log_database_id: str) -> None:
        self.client = Client(auth=api_key)
        self.log_database_id = log_database_id

    def save_pipeline_result(
        self,
        title: str,
        theme: ThemeResult | None = None,
        script: ScriptResult | None = None,
        video: VideoResult | None = None,
        upload: UploadResult | None = None,
    ) -> str:
        """パイプライン結果を1ページにまとめてNotionに保存。ページURLを返す。"""

        # ステータス判定
        if upload:
            status = "YouTube投稿済"
        elif video:
            status = "動画完成"
        elif script:
            status = "台本完成"
        else:
            status = "テーマ選定済"

        # プロパティ（titleのみ。他はページ本文に記載）
        props: dict = {
            "title": {"title": [{"text": {"content": f"[{status}] {title}"}}]},
        }

        # ページ本文ブロック
        blocks = self._build_blocks(title, theme, script, video, upload)

        # Notionページ作成（ブロックは50件ずつ分割してappend）
        page = self.client.pages.create(
            parent={"database_id": self.log_database_id},
            properties=props,
            children=blocks[:100],
        )
        page_id = page["id"]
        page_url = page["url"]

        # 台本が長い場合は続きをappend
        if len(blocks) > 100:
            for i in range(100, len(blocks), 100):
                self.client.blocks.children.append(
                    block_id=page_id,
                    children=blocks[i:i+100],
                )

        logger.info(f"Notion保存完了: {page_url}")
        return page_url

    def _build_blocks(
        self,
        title: str,
        theme: ThemeResult | None,
        script: ScriptResult | None,
        video: VideoResult | None,
        upload: UploadResult | None,
    ) -> list[dict]:
        blocks = []

        # ============ テーマ選定 ============
        if theme:
            blocks.append(_h2("🎯 テーマ選定"))
            if theme.selected_title:
                blocks.append(_bullet(f"選択タイトル: {theme.selected_title}"))

            if theme.reference_videos:
                blocks.append(_h3("参考にした高再生数動画"))
                for v in theme.reference_videos[:5]:
                    blocks.append(_bullet(f"{v.view_count:,}回 | {v.title} ({v.channel})"))

            blocks.append(_h3("タイトル候補"))
            for i, c in enumerate(theme.candidates, 1):
                blocks.append(_bullet(f"{i}. [{c.estimated_ctr}] {c.title} ({c.hook_type})"))
            blocks.append(_divider())

        # ============ 台本 ============
        if script:
            blocks.append(_h2("📝 台本"))
            blocks.append(_bullet(f"文字数: {script.char_count}文字"))
            blocks.append(_bullet(f"レビュー回数: {script.revision_count}回"))
            if script.review_history:
                last = script.review_history[-1]
                blocks.append(_bullet(
                    f"最終スコア: {last.total}/20 "
                    f"(hook={last.hook_score}, style={last.style_score}, "
                    f"length={last.length_score}, structure={last.structure_score})"
                ))
            blocks.append(_divider())

            # 台本本文（2000文字ずつ分割）
            blocks.append(_h3("台本本文"))
            text = script.script
            for i in range(0, len(text), 1800):
                blocks.append(_para(text[i:i+1800]))
            blocks.append(_divider())

        # ============ 動画 ============
        if video:
            blocks.append(_h2("🎬 動画"))
            blocks.append(_bullet(f"動画ファイル: {video.video_path}"))
            blocks.append(_bullet(f"音声ファイル: {video.audio_path}"))
            blocks.append(_bullet(f"サムネイル: {video.thumbnail_path}"))
            blocks.append(_bullet(f"動画時間: {video.duration_sec:.1f}秒"))
            blocks.append(_divider())

        # ============ YouTube投稿 ============
        if upload:
            blocks.append(_h2("▶️ YouTube投稿"))
            blocks.append(_bullet(f"動画URL: {upload.video_url}"))
            blocks.append(_bullet(f"ステータス: {upload.status}"))

        return blocks
