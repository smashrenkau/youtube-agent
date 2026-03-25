"""TTSプロバイダーの共通インターフェース。"""
from abc import ABC, abstractmethod
from pathlib import Path


class BaseTTS(ABC):
    """テキスト→音声変換の抽象基底クラス。"""

    @abstractmethod
    def synthesize(self, text: str, output_path: Path) -> Path:
        """テキストを音声ファイルに変換して保存。保存パスを返す。"""
        ...

    def get_duration(self, audio_path: Path) -> float:
        """音声ファイルの長さ（秒）を返す。"""
        try:
            from moviepy import AudioFileClip
            with AudioFileClip(str(audio_path)) as clip:
                return clip.duration
        except Exception:
            return 0.0
