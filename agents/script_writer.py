"""台本作成エージェント（自己レビューループ付き）。"""
import logging
from datetime import datetime
from pathlib import Path

from agents.base_agent import BaseAgent
from config.settings import get_settings
from models.schemas import ReviewScore, ScriptRequest, ScriptResult
from rag.retriever import Retriever
from notion.reporter import NotionReporter

logger = logging.getLogger(__name__)

MAX_REVISIONS = 3
APPROVAL_THRESHOLD = 16


class ScriptWriterAgent(BaseAgent):
    """初稿生成 → 自己レビュー → 修正を最大3回繰り返して台本をブラッシュアップ。"""

    def __init__(self, retriever: Retriever | None = None) -> None:
        super().__init__(retriever)
        settings = get_settings()
        self.output_dir = Path(settings.scripts_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Notion保存（log_database_idが設定されていれば有効）
        self.reporter: NotionReporter | None = None
        if settings.notion_log_database_id:
            self.reporter = NotionReporter(
                api_key=settings.notion_api_key.get_secret_value(),
                log_database_id=settings.notion_log_database_id,
            )

    def run(self, request: ScriptRequest) -> ScriptResult:
        logger.info(f"台本作成開始: title={request.title}")

        # RAGでナレッジ取得
        query = f"{request.title} ナレッジ 話し方 構成 スクリプト"
        knowledge = self._retrieve_knowledge(query)

        # 初稿生成
        script = self._generate_draft(request, knowledge)
        revision_count = 0
        review_history: list[ReviewScore] = []

        # 自己レビューループ
        for i in range(MAX_REVISIONS):
            logger.info(f"レビューラウンド {i + 1}/{MAX_REVISIONS}")
            review = self._review_script(request, script)
            review_history.append(review)

            logger.info(
                f"  スコア: {review.total}/20 "
                f"(hook={review.hook_score}, style={review.style_score}, "
                f"length={review.length_score}, structure={review.structure_score})"
            )

            if review.approved:
                logger.info("  ✓ レビュー承認")
                break

            logger.info(f"  修正が必要: {review.feedback[:80]}...")
            script = self._revise_script(request, script, review, knowledge)
            revision_count += 1

        else:
            # 最大回数に達した場合は最高スコアのものを採用（実質最終稿）
            logger.warning(f"最大レビュー回数({MAX_REVISIONS})に達しました。最終稿を採用します。")

        # ローカル保存
        output_path = self._save_script(request.title, script)
        logger.info(f"台本保存完了: {output_path}")

        result = ScriptResult(
            title=request.title,
            script=script,
            char_count=len(script),
            revision_count=revision_count,
            review_history=review_history,
            output_path=str(output_path),
        )

        # Notion保存
        if self.reporter:
            try:
                notion_url = self.reporter.save_pipeline_result(
                    title=request.title,
                    script=result,
                )
                logger.info(f"Notion保存完了: {notion_url}")
            except Exception as e:
                logger.warning(f"Notion保存失敗（ローカル保存は成功）: {e}")

        return result

    def _generate_draft(self, request: ScriptRequest, knowledge: str) -> str:
        template = self._load_prompt("script_writer")
        prompt = template.format(
            knowledge_context=knowledge or "（ナレッジなし）",
            title=request.title,
            target_chars=request.target_chars,
            style_notes=request.style_notes or "特になし",
        )
        logger.info("  初稿生成中...")
        return self._call_claude(prompt, max_tokens=8192)

    def _review_script(self, request: ScriptRequest, script: str) -> ReviewScore:
        template = self._load_prompt("script_reviewer")
        prompt = template.format(
            title=request.title,
            target_chars=request.target_chars,
            actual_chars=len(script),
            script=script,
        )
        raw = self._call_claude(prompt, max_tokens=3000)
        data = self._parse_json_response(raw)

        return ReviewScore(
            hook_score=data["hook_score"],
            style_score=data["style_score"],
            length_score=data["length_score"],
            structure_score=data["structure_score"],
            total=data["total"],
            feedback=data["feedback"],
            approved=data["approved"],
        )

    def _revise_script(
        self,
        request: ScriptRequest,
        current_script: str,
        review: ReviewScore,
        knowledge: str,
    ) -> str:
        """レビューフィードバックを反映して台本を修正。マルチターンで文脈を保持。"""
        messages = [
            {
                "role": "user",
                "content": (
                    f"以下の台本を作成してください。\n\n"
                    f"タイトル: {request.title}\n"
                    f"目標文字数: {request.target_chars}文字\n\n"
                    f"ナレッジ:\n{knowledge or '（なし）'}"
                ),
            },
            {"role": "assistant", "content": current_script},
            {
                "role": "user",
                "content": (
                    f"以下のレビューフィードバックに基づいて台本を修正してください。\n\n"
                    f"スコア: {review.total}/20\n"
                    f"フィードバック: {review.feedback}\n\n"
                    f"改善した台本のみを出力してください。"
                ),
            },
        ]
        return self._call_claude("", messages=messages, max_tokens=8192)

    def _save_script(self, title: str, script: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:50]
        filename = f"{timestamp}_{safe_title}.md"
        path = self.output_dir / filename

        content = f"# {title}\n\n{script}"
        path.write_text(content, encoding="utf-8")
        return path
