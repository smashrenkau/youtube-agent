"""生成物をローカルファイルに保存するモジュール。"""
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _to_dirname(title: str) -> str:
    """タイトルをディレクトリ名に使える形式に変換する。
    macOSで使えない文字（/ : \0 改行）のみ除去し、タイトルそのままに近い名前にする。
    """
    dirname = re.sub(r'[/:\x00\n\r]', '', title)
    return dirname[:60].strip()


class LocalStorage:
    """タイトル・台本・スライドをローカルファイルに保存する。

    構造:
        base_dir/
            {タイトル}/
                script_filming.txt
                script_slide.txt
                reference_videos.json
                slides.json
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_existing_titles(self) -> list[str]:
        """保存済みタイトル一覧をディレクトリ名から取得する。"""
        return [
            d.name
            for d in sorted(self.base_dir.iterdir())
            if d.is_dir()
        ]

    def save_title(self, title: str) -> str:
        """タイトルディレクトリを作成してディレクトリ名を返す。"""
        dirname = _to_dirname(title)
        (self.base_dir / dirname).mkdir(parents=True, exist_ok=True)
        logger.info(f"タイトル保存: {title} → {dirname}/")
        return dirname

    def save_script(self, slug: str, script: str, filename: str = "script.txt") -> None:
        path = self.base_dir / slug / filename
        path.write_text(script, encoding="utf-8")
        logger.info(f"台本保存: {path}")

    def save_reference_videos(self, slug: str, videos: list[dict]) -> None:
        path = self.base_dir / slug / "reference_videos.json"
        path.write_text(
            json.dumps(videos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"参照動画保存: {len(videos)}件")

    def save_slides(self, slug: str, slides: list[dict]) -> None:
        path = self.base_dir / slug / "slides.json"
        path.write_text(
            json.dumps(slides, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"スライド保存: {len(slides)}枚")
