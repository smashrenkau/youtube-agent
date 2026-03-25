"""テーマ選定エージェント（YouTube検索 + RAG + Claude）。"""
import logging

from agents.base_agent import BaseAgent
from models.schemas import ThemeRequest, ThemeResult, TitleCandidate
from rag.retriever import Retriever

logger = logging.getLogger(__name__)


class ThemeSelectorAgent(BaseAgent):
    """YouTube高再生数動画を参照 + RAGナレッジ + Claudeでタイトルを生成するエージェント。"""

    def __init__(
        self,
        retriever: Retriever | None = None,
        youtube_searcher=None,  # YouTubeSearcher | None
    ) -> None:
        super().__init__(retriever)
        self.youtube_searcher = youtube_searcher

    def run(self, request: ThemeRequest) -> ThemeResult:
        logger.info(f"テーマ選定開始: purpose={request.purpose}, genre={request.genre}")

        # Step1: YouTubeで高再生数動画を検索
        reference_videos = []
        youtube_results_text = "（YouTube検索スキップ）"

        if self.youtube_searcher and request.keywords:
            logger.info(f"YouTube検索キーワード: {request.keywords}")
            reference_videos = self.youtube_searcher.search_top_videos(
                keywords=request.keywords,
                max_per_keyword=5,
            )
            youtube_results_text = self.youtube_searcher.format_for_prompt(reference_videos)
        elif not request.keywords:
            logger.info("キーワード未指定のためYouTube検索をスキップ")

        # Step2: RAGでナレッジ取得
        query = f"{request.genre} YouTube タイトル 視聴者 {request.purpose}"
        knowledge = self._retrieve_knowledge(query)

        # Step3: プロンプト構築してClaude呼び出し
        template = self._load_prompt("theme_selector")
        prompt = template.format(
            youtube_results=youtube_results_text,
            knowledge_context=knowledge or "（ナレッジなし）",
            count=request.count,
            purpose=request.purpose,
            genre=request.genre,
        )

        raw = self._call_claude(prompt, max_tokens=2048)
        data = self._parse_json_response(raw)

        candidates = [
            TitleCandidate(
                title=c["title"],
                hook_type=c.get("hook_type", "不明"),
                estimated_ctr=c.get("estimated_ctr", "Medium"),
                reasoning=c.get("reasoning", ""),
                source_video_id=c.get("source_video_id"),
            )
            for c in data.get("candidates", [])
        ]

        logger.info(f"タイトル候補 {len(candidates)} 件生成完了")
        return ThemeResult(candidates=candidates, reference_videos=reference_videos)
