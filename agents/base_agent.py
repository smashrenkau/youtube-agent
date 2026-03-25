"""全エージェント共通の基底クラス。"""
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path

import anthropic

from config.settings import get_settings
from rag.retriever import Retriever

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Anthropicクライアント・RAGリトリーバーを保持する基底クラス。"""

    def __init__(self, retriever: Retriever | None = None) -> None:
        settings = get_settings()
        self.client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
        self.model = settings.anthropic_model
        self.retriever = retriever

    def _load_prompt(self, name: str) -> str:
        """config/prompts/ からプロンプトテンプレートを読み込む。"""
        path = Path("config/prompts") / f"{name}.txt"
        return path.read_text(encoding="utf-8")

    def _retrieve_knowledge(self, query: str) -> str:
        """RAGリトリーバーからナレッジを取得。リトリーバーが未設定なら空文字を返す。"""
        if self.retriever is None:
            return "（ナレッジベースは設定されていません）"
        return self.retriever.retrieve(query)

    def _call_claude(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        messages: list[dict] | None = None,
    ) -> str:
        """Claude APIを呼び出してテキストを返す。"""
        start = time.time()

        if messages is None:
            messages = [{"role": "user", "content": prompt}]

        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        elapsed = time.time() - start

        usage = response.usage
        logger.debug(
            f"Claude API: {elapsed:.1f}秒, "
            f"input={usage.input_tokens}, output={usage.output_tokens}"
        )

        return response.content[0].text

    def _parse_json_response(self, text: str) -> dict:
        """レスポンステキストからJSONを抽出・パース。"""
        # コードブロックを除去
        cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()

        # JSON部分を抽出
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSONパース失敗: {e}\n---\n{text}\n---")
            raise ValueError(f"Claude APIのレスポンスをJSONとしてパースできませんでした: {e}") from e

    @abstractmethod
    def run(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """各エージェントの主処理。サブクラスで実装する。"""
        ...
