"""サムネイル画像を生成するモジュール。"""
import json
import logging
import textwrap
from pathlib import Path

logger = logging.getLogger(__name__)


class ThumbnailGenerator:
    """Pillowを使ってYouTubeサムネイルを生成する。"""

    def __init__(self, template_name: str = "default_template") -> None:
        template_path = Path("video/templates") / f"{template_name}.json"
        with open(template_path, encoding="utf-8") as f:
            self.template = json.load(f)["thumbnail"]

    def generate(self, title: str, output_path: Path) -> Path:
        """タイトルテキストからサムネイルを生成。"""
        from PIL import Image, ImageDraw, ImageFont

        tmpl = self.template
        width, height = tmpl["width"], tmpl["height"]
        bg_color = tmpl["background_color"]
        accent_color = tmpl["accent_color"]
        title_color = tmpl["title_color"]
        font_size = tmpl["title_font_size"]

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # アクセントライン
        draw.rectangle([(0, height - 8), (width, height)], fill=accent_color)
        draw.rectangle([(0, 0), (width, 8)], fill=accent_color)

        # タイトルテキスト（折り返し）
        try:
            font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", font_size)
        except Exception:
            font = ImageFont.load_default()

        wrapped = "\n".join(textwrap.wrap(title, width=18))
        # テキストを中央配置
        bbox = draw.textbbox((0, 0), wrapped, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # シャドウ
        draw.text((x + 3, y + 3), wrapped, fill="#000000", font=font, align="center")
        draw.text((x, y), wrapped, fill=title_color, font=font, align="center")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=95)
        logger.info(f"サムネイル生成完了: {output_path}")
        return output_path
