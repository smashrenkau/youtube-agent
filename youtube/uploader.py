"""YouTube Data API v3 で動画をアップロードするモジュール。"""
import logging
import os
from pathlib import Path
from typing import Literal

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"


class YouTubeUploader:
    """OAuth2認証 + YouTube APIで動画をアップロード。"""

    def __init__(
        self,
        client_secrets_path: str = "credentials/client_secrets.json",
        token_path: str = "credentials/token.json",
    ) -> None:
        self.client_secrets_path = client_secrets_path
        self.token_path = token_path
        self._service = None

    def _get_service(self):  # type: ignore[no-untyped-def]
        if self._service is not None:
            return self._service

        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # トークンを保存
            Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

        self._service = build(YOUTUBE_API_SERVICE, YOUTUBE_API_VERSION, credentials=creds)
        return self._service

    def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        privacy: Literal["private", "unlisted", "public"] = "private",
    ) -> dict:
        """動画をアップロードしてビデオIDとURLを返す。"""
        service = self._get_service()

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            video_path,
            chunksize=1024 * 1024,  # 1MB チャンク
            resumable=True,
        )

        logger.info(f"YouTube アップロード開始: {title}")
        request = service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"  アップロード進捗: {progress}%")

        video_id = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"アップロード完了: {video_url}")

        return {"video_id": video_id, "video_url": video_url}

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> None:
        """動画のサムネイルを設定。"""
        service = self._get_service()
        service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path),
        ).execute()
        logger.info(f"サムネイル設定完了: {video_id}")
