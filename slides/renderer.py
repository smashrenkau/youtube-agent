"""PlaywrightでHTMLスライドをPNG画像にレンダリング。"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SlideRenderer:
    """HTML文字列を受け取り1920x1080のPNG画像として保存する。"""

    def render(self, html: str, output_path: Path) -> Path:
        from playwright.sync_api import sync_playwright

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.set_content(html, wait_until="networkidle")
            page.screenshot(path=str(output_path), full_page=False)
            browser.close()

        logger.debug(f"スライドレンダリング完了: {output_path}")
        return output_path

    def render_batch(self, slides: list[tuple[str, Path]]) -> list[Path]:
        """複数スライドをまとめてレンダリング。(html, output_path)のリストを受け取る。"""
        from playwright.sync_api import sync_playwright

        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            for html, output_path in slides:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                page.set_content(html, wait_until="networkidle")
                page.screenshot(path=str(output_path), full_page=False)
                results.append(output_path)
                logger.debug(f"  レンダリング: {output_path.name}")

            browser.close()

        logger.info(f"スライド {len(results)} 枚レンダリング完了")
        return results
