"""動画生成エージェント（スライド生成 + タイムスタンプTTS + 動画編集）。"""
import logging
from datetime import datetime
from pathlib import Path

from agents.base_agent import BaseAgent
from config.settings import get_settings
from models.schemas import VideoRequest, VideoResult
from rag.retriever import Retriever
from tts.base_tts import BaseTTS
from video.editor import VideoEditor
from video.thumbnail import ThumbnailGenerator

logger = logging.getLogger(__name__)


class VideoGeneratorAgent(BaseAgent):
    """台本からスライド・音声・動画を生成するエージェント。"""

    def __init__(
        self,
        tts: BaseTTS | None = None,
        retriever: Retriever | None = None,
        generate_slides: bool = True,
    ) -> None:
        super().__init__(retriever)
        settings = get_settings()

        self.tts = tts or self._init_tts(settings)
        self.generate_slides = generate_slides
        self.audio_dir = Path(settings.audio_output_dir)
        self.video_dir = Path(settings.video_output_dir)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)

    def run(self, request: VideoRequest) -> VideoResult:
        logger.info(f"動画生成開始: {request.title}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in request.title)[:40]
        base_name = f"{timestamp}_{safe_title}"

        # Step 1: スライド生成
        slide_images = None
        if self.generate_slides:
            slide_images = self._generate_slides(request.script, base_name)

        # Step 2: TTS音声生成（タイムスタンプ付き）
        audio_path = self.audio_dir / f"{base_name}.mp3"
        word_timestamps = None

        if hasattr(self.tts, "synthesize_with_timestamps"):
            try:
                audio_path, word_timestamps = self.tts.synthesize_with_timestamps(
                    request.script, audio_path
                )
                logger.info(f"タイムスタンプ取得: {len(word_timestamps)}単語")
            except Exception as e:
                logger.warning(f"タイムスタンプ取得失敗、通常合成にフォールバック: {e}")
                self.tts.synthesize(request.script, audio_path)
        else:
            self.tts.synthesize(request.script, audio_path)

        # Step 3: 動画生成
        editor = VideoEditor(request.template_name)
        video_path = self.video_dir / f"{base_name}.mp4"
        video_path, duration = editor.create_video(
            audio_path=audio_path,
            script=request.script,
            output_path=video_path,
            slide_images=slide_images,
            word_timestamps=word_timestamps,
        )

        # Step 4: サムネイル生成
        thumbnail_path = self.video_dir / f"{base_name}_thumbnail.jpg"
        ThumbnailGenerator(request.template_name).generate(request.title, thumbnail_path)

        logger.info(f"動画生成完了: {video_path} ({duration:.1f}秒)")
        return VideoResult(
            video_path=str(video_path),
            audio_path=str(audio_path),
            thumbnail_path=str(thumbnail_path),
            duration_sec=duration,
        )

    def _generate_slides(self, script: str, base_name: str) -> list[dict] | None:
        try:
            from slides.slide_agent import SlideGeneratorAgent
            slide_dir = self.video_dir / f"{base_name}_slides"
            agent = SlideGeneratorAgent()
            return agent.generate_slides(script, slide_dir)
        except Exception as e:
            logger.warning(f"スライド生成失敗、背景なしで続行: {e}")
            return None

    def _init_tts(self, settings) -> BaseTTS:  # type: ignore[no-untyped-def]
        if settings.tts_provider == "elevenlabs":
            from tts.elevenlabs_tts import ElevenLabsTTS
            return ElevenLabsTTS(
                api_key=settings.elevenlabs_api_key.get_secret_value(),
                voice_id=settings.elevenlabs_voice_id,
                speed=1.3,
            )
        else:
            from tts.openai_tts import OpenAITTS
            return OpenAITTS(api_key=settings.openai_api_key.get_secret_value())
