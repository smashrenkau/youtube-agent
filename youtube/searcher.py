"""YouTube Data API v3 で動画を検索・分析するモジュール。"""
import logging
from googleapiclient.discovery import build

from models.schemas import YouTubeVideoInfo

logger = logging.getLogger(__name__)


class YouTubeSearcher:
    """キーワードで高再生数動画を検索し、タイトル分析に使う情報を返す。"""

    def __init__(self, api_key: str) -> None:
        self.service = build("youtube", "v3", developerKey=api_key)

    def search_top_videos(
        self,
        keywords: list[str],
        max_per_keyword: int = 5,
        region_code: str = "JP",
    ) -> list[YouTubeVideoInfo]:
        """キーワードリストで検索し、再生数上位の動画をまとめて返す。"""
        all_videos: list[YouTubeVideoInfo] = []
        seen_ids: set[str] = set()

        for keyword in keywords:
            logger.info(f"YouTube検索: '{keyword}'")
            videos = self._search_by_keyword(keyword, max_per_keyword, region_code)
            for v in videos:
                if v.video_id not in seen_ids:
                    all_videos.append(v)
                    seen_ids.add(v.video_id)

        # 再生数で降順ソート
        all_videos.sort(key=lambda v: v.view_count, reverse=True)
        logger.info(f"合計 {len(all_videos)} 件の参考動画を取得")
        return all_videos

    def _search_by_keyword(
        self,
        keyword: str,
        max_results: int,
        region_code: str,
    ) -> list[YouTubeVideoInfo]:
        """1キーワードで検索して動画リストを返す。"""
        try:
            # Step1: 検索（video_idリスト取得）
            search_response = self.service.search().list(
                part="snippet",
                q=keyword,
                type="video",
                order="viewCount",
                maxResults=max_results,
                regionCode=region_code,
            ).execute()

            video_ids = [
                item["id"]["videoId"]
                for item in search_response.get("items", [])
            ]
            if not video_ids:
                return []

            # Step2: 再生数取得（statistics）
            stats_response = self.service.videos().list(
                part="statistics,snippet",
                id=",".join(video_ids),
            ).execute()

            videos = []
            for item in stats_response.get("items", []):
                video_id = item["id"]
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                view_count = int(stats.get("viewCount", 0))

                videos.append(YouTubeVideoInfo(
                    title=snippet["title"],
                    channel=snippet["channelTitle"],
                    view_count=view_count,
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    published_at=snippet.get("publishedAt", ""),
                ))

            return videos

        except Exception as e:
            logger.warning(f"YouTube検索エラー (keyword='{keyword}'): {e}")
            return []

    def format_for_prompt(self, videos: list[YouTubeVideoInfo], top_n: int = 10) -> str:
        """プロンプトに埋め込む形式に整形。"""
        if not videos:
            return "（YouTube検索結果なし）"

        lines = []
        for i, v in enumerate(videos[:top_n], 1):
            view_str = f"{v.view_count:,}回"
            lines.append(f"{i}. 【{view_str}】{v.title}（{v.channel}）")

        return "\n".join(lines)
