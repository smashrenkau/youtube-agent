"""生成物をローカルファイルに保存するモジュール。"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _slugify(title: str) -> str:
    """タイトルをファイル名に使えるスラグに変換する。"""
    slug = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    slug = re.sub(r"\s+", "_", slug)
    return slug[:60]


class LocalStorage:
    """タイトル・台本・スライドをローカルファイルに保存する。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.titles_file = self.base_dir / "titles.json"

    def _load_titles_data(self) -> list[dict]:
        if not self.titles_file.exists():
            return []
        return json.loads(self.titles_file.read_text(encoding="utf-8"))

    def _save_titles_data(self, data: list[dict]) -> None:
        self.titles_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_existing_titles(self) -> list[str]:
        return [entry["title"] for entry in self._load_titles_data()]

    def save_title(self, title: str) -> str:
        """タイトルを保存してスラグ（page_id代わり）を返す。"""
        slug = _slugify(title)
        (self.base_dir / slug).mkdir(parents=True, exist_ok=True)

        data = self._load_titles_data()
        if not any(e["title"] == title for e in data):
            data.append({
                "title": title,
                "slug": slug,
                "created_at": datetime.now().isoformat(),
            })
            self._save_titles_data(data)

        logger.info(f"タイトル保存: {title}")
        return slug

    def save_script(self, slug: str, script: str) -> None:
        path = self.base_dir / slug / "script.txt"
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
