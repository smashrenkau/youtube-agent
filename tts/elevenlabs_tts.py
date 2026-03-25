"""ElevenLabs TTSの実装（タイムスタンプ対応・速度調整付き）。"""
import logging
import subprocess
from pathlib import Path

from tts.base_tts import BaseTTS

logger = logging.getLogger(__name__)


class ElevenLabsTTS(BaseTTS):
    """ElevenLabs APIを使ったTTS実装。タイムスタンプ取得・速度調整対応。"""

    def __init__(self, api_key: str, voice_id: str, speed: float = 1.3) -> None:
        from elevenlabs import ElevenLabs
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.speed = speed  # 再生速度（デフォルト1.3倍）

    def synthesize(self, text: str, output_path: Path) -> Path:
        """テキストを音声化して保存。speed倍速で出力。"""
        logger.info(f"ElevenLabs TTS: {len(text)}文字を音声化中...")

        audio = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            voice_settings={
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path = output_path.with_suffix(".raw.mp3")

        with open(raw_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        # 速度調整（ffmpegで atempo フィルタ）
        if abs(self.speed - 1.0) > 0.01:
            self._adjust_speed(raw_path, output_path, self.speed)
            raw_path.unlink()
        else:
            raw_path.rename(output_path)

        logger.info(f"音声保存完了: {output_path} ({self.speed}倍速)")
        return output_path

    def synthesize_with_timestamps(self, text: str, output_path: Path) -> tuple[Path, list[dict]]:
        """テキストを音声化しつつ、単語レベルのタイムスタンプも取得。

        Returns:
            (audio_path, alignment)
            alignment: [{"text": "word", "start": 0.0, "end": 0.3}, ...]
        """
        logger.info(f"ElevenLabs TTS (タイムスタンプ付き): {len(text)}文字を音声化中...")

        response = self.client.text_to_speech.convert_with_timestamps(
            voice_id=self.voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            voice_settings={
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path = output_path.with_suffix(".raw.mp3")

        # 音声バイナリ保存
        import base64
        audio_bytes = base64.b64decode(response.audio_base64)
        raw_path.write_bytes(audio_bytes)

        # アライメント情報を抽出
        alignment = self._extract_alignment(response.alignment)

        # 速度調整
        if abs(self.speed - 1.0) > 0.01:
            self._adjust_speed(raw_path, output_path, self.speed)
            raw_path.unlink()
            # タイムスタンプも速度補正
            alignment = [
                {**a, "start": a["start"] / self.speed, "end": a["end"] / self.speed}
                for a in alignment
            ]
        else:
            raw_path.rename(output_path)

        logger.info(f"音声保存完了: {output_path} ({self.speed}倍速, {len(alignment)}単語)")
        return output_path, alignment

    def _extract_alignment(self, alignment_obj) -> list[dict]:
        """ElevenLabsのアライメントオブジェクトを辞書リストに変換。"""
        if alignment_obj is None:
            return []

        result = []
        chars = getattr(alignment_obj, "characters", []) or []
        starts = getattr(alignment_obj, "character_start_times_seconds", []) or []
        ends = getattr(alignment_obj, "character_end_times_seconds", []) or []

        # 文字レベルを単語レベルにまとめる
        current_word = ""
        word_start = 0.0
        word_end = 0.0

        for char, start, end in zip(chars, starts, ends):
            if char == " " or char == "\n":
                if current_word:
                    result.append({"text": current_word, "start": word_start, "end": word_end})
                    current_word = ""
            else:
                if not current_word:
                    word_start = start
                current_word += char
                word_end = end

        if current_word:
            result.append({"text": current_word, "start": word_start, "end": word_end})

        return result

    def _adjust_speed(self, input_path: Path, output_path: Path, speed: float) -> None:
        """ffmpegのatempoフィルタで音声速度を調整。"""
        # atempoは0.5〜2.0の範囲しか対応していないため、2.0以上は連結
        if speed <= 2.0:
            atempo = f"atempo={speed}"
        else:
            atempo = f"atempo=2.0,atempo={speed/2.0}"

        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-filter:a", atempo,
            "-vn", str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"ffmpeg速度調整失敗: {result.stderr}")
            # フォールバック：そのままコピー
            import shutil
            shutil.copy(input_path, output_path)
