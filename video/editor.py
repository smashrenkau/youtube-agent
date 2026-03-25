"""MoviePy v2 + スライド画像を使った動画生成モジュール。"""
import json
import logging
import re
import textwrap
from pathlib import Path

logger = logging.getLogger(__name__)

JAPANESE_FONTS = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴ ProN W6.ttc",
    "/Library/Fonts/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/AppleGothic.ttf",
]


def _find_japanese_font() -> str | None:
    for path in JAPANESE_FONTS:
        if Path(path).exists():
            return path
    return None


class VideoEditor:
    """スライド画像 + 音声 + 同期字幕から動画を生成する。"""

    def __init__(self, template_name: str = "default_template") -> None:
        template_path = Path("video/templates") / f"{template_name}.json"
        with open(template_path, encoding="utf-8") as f:
            self.template = json.load(f)

    def create_video(
        self,
        audio_path: Path,
        script: str,
        output_path: Path,
        slide_images: list[dict] | None = None,
        word_timestamps: list[dict] | None = None,
    ) -> tuple[Path, float]:
        """動画を生成する。

        Args:
            audio_path: 音声ファイル
            script: 台本テキスト
            output_path: 出力先MP4
            slide_images: [{"png_path": str, "script_fragment": str}, ...]
            word_timestamps: [{"text": str, "start": float, "end": float}, ...]
        """
        from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, TextClip

        logger.info("動画生成開始")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        tmpl = self.template
        width, height = tmpl["resolution"]
        fps = tmpl["fps"]

        audio_clip = AudioFileClip(str(audio_path))
        duration = audio_clip.duration

        # ベースクリップ（スライドあり or 無地背景）
        if slide_images:
            base_clip = self._build_slide_track(slide_images, duration, width, height)
        else:
            bg_color = self._hex_to_rgb(tmpl["background"]["value"])
            base_clip = ColorClip(size=(width, height), color=bg_color, duration=duration)

        # 字幕クリップ
        subtitle_clips = self._build_subtitle_track(
            script, duration, width, height, tmpl, word_timestamps
        )

        # 合成
        all_clips = [base_clip] + subtitle_clips
        video = CompositeVideoClip(all_clips, size=(width, height)).with_audio(audio_clip)

        logger.info(f"動画エンコード中: {output_path}")
        video.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )

        audio_clip.close()
        video.close()
        logger.info(f"動画生成完了: {output_path} ({duration:.1f}秒)")
        return output_path, duration

    def _build_slide_track(
        self,
        slide_images: list[dict],
        total_duration: float,
        width: int,
        height: int,
    ):
        """スライド画像を等分割でタイムラインに並べる。"""
        from moviepy import ColorClip, ImageClip, CompositeVideoClip

        n = len(slide_images)
        if n == 0:
            bg_color = self._hex_to_rgb(self.template["background"]["value"])
            return ColorClip(size=(width, height), color=bg_color, duration=total_duration)

        slide_duration = total_duration / n
        clips = []

        for i, slide in enumerate(slide_images):
            png_path = slide["png_path"]
            start = i * slide_duration
            dur = slide_duration if i < n - 1 else (total_duration - start)

            try:
                img_clip = (
                    ImageClip(png_path)
                    .resized((width, height))
                    .with_start(start)
                    .with_duration(dur)
                )
                clips.append(img_clip)
            except Exception as e:
                logger.warning(f"スライド{i+1}読み込み失敗: {e}")
                bg_color = self._hex_to_rgb(self.template["background"]["value"])
                fallback = ColorClip(size=(width, height), color=bg_color, duration=dur).with_start(start)
                clips.append(fallback)

        return CompositeVideoClip(clips, size=(width, height)).with_duration(total_duration)

    def _build_subtitle_track(
        self,
        script: str,
        duration: float,
        width: int,
        height: int,
        tmpl: dict,
        word_timestamps: list[dict] | None,
    ) -> list:
        """字幕クリップのリストを返す。"""
        font_path = _find_japanese_font()
        if not font_path:
            logger.warning("日本語フォントが見つからないため字幕なし")
            return []

        if word_timestamps:
            return self._subtitles_from_timestamps(word_timestamps, font_path, width, height, tmpl)
        else:
            return self._subtitles_from_script(script, duration, font_path, width, height, tmpl)

    def _subtitles_from_timestamps(
        self,
        word_timestamps: list[dict],
        font_path: str,
        width: int,
        height: int,
        tmpl: dict,
    ) -> list:
        """単語タイムスタンプから字幕クリップを生成（精密同期）。"""
        from moviepy import TextClip

        clips = []
        # 句点・改行で文をまとめる
        sentences = self._group_words_to_sentences(word_timestamps)

        for sent in sentences:
            text = sent["text"]
            start = sent["start"]
            dur = sent["end"] - sent["start"]
            if dur <= 0:
                continue

            wrapped = "\n".join(textwrap.wrap(text, width=tmpl["subtitle"]["max_chars_per_line"]))
            try:
                clip = (
                    TextClip(
                        font=font_path,
                        text=wrapped,
                        font_size=tmpl["font"]["size"],
                        color=tmpl["font"]["color"],
                        stroke_color=tmpl["font"]["stroke_color"],
                        stroke_width=tmpl["font"]["stroke_width"],
                        size=(width - 200, None),
                        method="caption",
                        text_align="center",
                        duration=dur,
                    )
                    .with_start(start)
                    .with_position(("center", height - 180))
                )
                clips.append(clip)
            except Exception as e:
                logger.warning(f"字幕スキップ: {e}")

        return clips

    def _subtitles_from_script(
        self,
        script: str,
        duration: float,
        font_path: str,
        width: int,
        height: int,
        tmpl: dict,
    ) -> list:
        """文字数比率で推定タイミングの字幕を生成（タイムスタンプ未使用時のフォールバック）。"""
        from moviepy import TextClip

        sentences = self._split_into_sentences(script)
        if not sentences:
            return []

        char_count = sum(len(s) for s in sentences)
        chars_per_sec = char_count / duration if duration > 0 else 5
        clips = []
        current_time = 0.0

        for sentence in sentences:
            if not sentence.strip():
                continue
            dur = max(len(sentence) / chars_per_sec, 0.5)
            wrapped = "\n".join(textwrap.wrap(sentence, width=tmpl["subtitle"]["max_chars_per_line"]))
            try:
                clip = (
                    TextClip(
                        font=font_path,
                        text=wrapped,
                        font_size=tmpl["font"]["size"],
                        color=tmpl["font"]["color"],
                        stroke_color=tmpl["font"]["stroke_color"],
                        stroke_width=tmpl["font"]["stroke_width"],
                        size=(width - 200, None),
                        method="caption",
                        text_align="center",
                        duration=dur,
                    )
                    .with_start(current_time)
                    .with_position(("center", height - 180))
                )
                clips.append(clip)
            except Exception as e:
                logger.warning(f"字幕スキップ: {e}")
            current_time += dur

        return clips

    def _group_words_to_sentences(self, word_timestamps: list[dict]) -> list[dict]:
        """単語タイムスタンプを文単位にまとめる。"""
        sentences = []
        current_words = []
        current_start = 0.0

        for w in word_timestamps:
            if not current_words:
                current_start = w["start"]
            current_words.append(w["text"])

            # 句読点・改行で区切る
            text_so_far = "".join(current_words)
            if any(text_so_far.endswith(p) for p in ["。", "！", "？", "\n", "、"]) or len(text_so_far) > 40:
                sentences.append({
                    "text": text_so_far,
                    "start": current_start,
                    "end": w["end"],
                })
                current_words = []

        if current_words:
            last = word_timestamps[-1]
            sentences.append({
                "text": "".join(current_words),
                "start": current_start,
                "end": last["end"],
            })

        return sentences

    def _split_into_sentences(self, text: str) -> list[str]:
        text = re.sub(r"【.+?】", "", text)
        sentences = re.split(r"(?<=[。！？\n])", text)
        return [s.strip() for s in sentences if s.strip()]

    def _hex_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return r, g, b
