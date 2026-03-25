"""OpenAI TTS実装（ElevenLabsのフォールバック）。"""
import logging
from pathlib import Path
from typing import Literal

from tts.base_tts import BaseTTS

logger = logging.getLogger(__name__)

VoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


class OpenAITTS(BaseTTS):
    """OpenAI APIを使ったTTS実装。"""

    def __init__(self, api_key: str, voice: VoiceType = "nova") -> None:
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.voice = voice

    def synthesize(self, text: str, output_path: Path) -> Path:
        logger.info(f"OpenAI TTS: {len(text)}文字を音声化中...")

        # OpenAI TTSは4096文字制限があるためチャンク分割
        chunks = self._split_text(text, max_chars=4000)
        audio_chunks: list[bytes] = []

        for i, chunk in enumerate(chunks):
            logger.debug(f"  チャンク {i + 1}/{len(chunks)}: {len(chunk)}文字")
            response = self.client.audio.speech.create(
                model="tts-1-hd",
                voice=self.voice,
                input=chunk,
            )
            audio_chunks.append(response.content)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if len(audio_chunks) == 1:
            output_path.write_bytes(audio_chunks[0])
        else:
            # 複数チャンクを結合（単純バイト結合）
            with open(output_path, "wb") as f:
                for chunk_bytes in audio_chunks:
                    f.write(chunk_bytes)

        logger.info(f"音声保存完了: {output_path}")
        return output_path

    def _split_text(self, text: str, max_chars: int) -> list[str]:
        """テキストを文単位で分割。"""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current = ""
        for sentence in text.replace("。", "。\n").split("\n"):
            if len(current) + len(sentence) > max_chars:
                if current:
                    chunks.append(current.strip())
                current = sentence
            else:
                current += sentence

        if current.strip():
            chunks.append(current.strip())

        return chunks
