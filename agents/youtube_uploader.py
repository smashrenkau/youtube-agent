"""YouTube投稿エージェント。"""
import logging

from agents.base_agent import BaseAgent
from config.settings import get_settings
from models.schemas import UploadRequest, UploadResult
from rag.retriever import Retriever
from youtube.uploader import YouTubeUploader

logger = logging.getLogger(__name__)


class YouTubeUploaderAgent(BaseAgent):
    """動画ファイルをYouTubeに投稿するエージェント。"""

    def __init__(self, retriever: Retriever | None = None) -> None:
        super().__init__(retriever)
        settings = get_settings()
        self.uploader = YouTubeUploader(
            client_secrets_path=settings.youtube_client_secrets_path,
            token_path=settings.youtube_token_path,
        )

    def run(self, request: UploadRequest) -> UploadResult:
        logger.info(f"YouTube投稿開始: {request.title}")

        result = self.uploader.upload(
            video_path=request.video_path,
            title=request.title,
            description=request.description,
            tags=request.tags,
            privacy=request.privacy,
        )

        if request.thumbnail_path:
            try:
                self.uploader.set_thumbnail(result["video_id"], request.thumbnail_path)
            except Exception as e:
                logger.warning(f"サムネイル設定失敗（投稿は成功）: {e}")

        return UploadResult(
            video_id=result["video_id"],
            video_url=result["video_url"],
            status="uploaded",
        )

    def generate_description(self, title: str, script: str) -> str:
        """台本のサマリーから動画説明文を生成。"""
        prompt = (
            f"以下のYouTube動画台本から、概要欄（説明文）を生成してください。\n\n"
            f"タイトル: {title}\n\n"
            f"台本（冒頭500文字）:\n{script[:500]}\n\n"
            f"要件:\n"
            f"- 200〜400文字\n"
            f"- 動画の内容を簡潔に説明\n"
            f"- 最後にチャンネル登録を促す一言\n"
            f"- ハッシュタグを3〜5個追加"
        )
        return self._call_claude(prompt, max_tokens=512)
