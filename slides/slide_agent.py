"""台本からManusレベルの高品質スライドを生成するエージェント。"""
import json
import logging
import re
import time
from pathlib import Path

from agents.base_agent import BaseAgent
from slides.renderer import SlideRenderer

logger = logging.getLogger(__name__)

SLIDE_DESIGN_PROMPT = '''あなたは世界トップレベルのプレゼンテーションデザイナーです。
以下の台本セクションを視覚的に表現する、Manus品質の美しいHTMLスライドを1枚生成してください。

## 台本セクション
タイトル: {section_title}
内容: {section_content}
スライド番号: {slide_num} / {total_slides}

## デザイン要件
- 解像度: 1920×1080px（必ずこのサイズに合わせる）
- 言っている内容を「図解・ダイアグラム・比較表・フロー・統計ビジュアル」などで視覚化する
- 毎回異なるレイアウトを使う（毎回同じ構図にしない）
- プロフェッショナルで洗練されたデザイン
- 日本語テキストを使用
- 背景は単色でなくグラデーション・形状・幾何学的要素を活用

## カラーパレット
- プライマリ: #1e3a5f（ダークネイビー）
- アクセント1: #e94560（レッド）
- アクセント2: #00b4d8（シアン）
- アクセント3: #f4a261（オレンジ）
- テキスト: #ffffff, #e0e0e0
- 背景ベース: #0a1628

## 使えるレイアウトタイプ（内容に最適なものを選ぶ）
- **比較型**: 2つの選択肢・対比を左右で見せる
- **フロー型**: プロセス・ステップを矢印でつなぐ
- **3柱型**: 3つのポイントを並列表示
- **強調型**: 1つの核心メッセージを大きく見せる（数字・キーワード）
- **問題→解決型**: 上段に問題、下段に解決策
- **アイコングリッド型**: アイコン＋テキストのグリッド
- **ピラミッド型**: 重要度の階層構造
- **タイムライン型**: 時系列の流れ

## 技術要件
- 完全なHTML（<!DOCTYPE html>から</html>まで）
- CSSはすべて<style>タグ内にインライン記述（クラス数は最小限に）
- 外部ライブラリ不使用（CSSのみ）
- body margin: 0, overflow: hidden
- フォント: system-ui または "Helvetica Neue", sans-serif
- 日本語はUnicode直接記述
- **CSSは簡潔に書く（1プロパティ1行でなく省略可）**
- **アニメーション・transitionは使わない（静的デザインのみ）**
- **合計で必ず</html>まで出力を完結させること**

## 出力
HTMLコードのみを出力してください。説明文は不要です。
```html
から始めて```で終わってください。
'''

SCRIPT_PARSER_PROMPT = '''以下のYouTube台本を、スライド用にセクション分割してください。

## 台本
{script}

## 指示
- 台本を意味のまとまりで6〜8セクションに分割する
- 各セクションには簡潔なタイトルと、そのセクションの内容要約を付ける
- オープニングとエンディングも含める

## 出力形式（JSONのみ）
{{
  "sections": [
    {{
      "title": "セクションタイトル（短く、キャッチーに）",
      "content": "このセクションで言っている内容の要約（100文字以内）",
      "script_fragment": "台本の該当部分（最初の50文字程度）",
      "slide_type_hint": "比較型|フロー型|3柱型|強調型|問題→解決型|アイコングリッド型|ピラミッド型|タイムライン型"
    }}
  ]
}}

JSONのみ出力してください。
'''


class SlideGeneratorAgent(BaseAgent):
    """台本を解析してManusレベルのHTMLスライドを生成するエージェント。"""

    def __init__(self) -> None:
        super().__init__()
        self.renderer = SlideRenderer()

    def run(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError("generate_slides() を使ってください")

    def generate_slides(self, script: str, output_dir: Path) -> list[dict]:
        """台本からスライドを生成し、PNGパスのリストを返す。

        Returns:
            list of {"slide_num": int, "title": str, "png_path": str, "script_fragment": str}
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step1: 台本をセクション分割
        logger.info("台本をセクション分割中...")
        sections = self._parse_sections(script)
        logger.info(f"  {len(sections)}セクションに分割")

        # Step2: 各セクションのHTMLスライドを生成
        slide_data = []
        html_slide_pairs = []

        for i, section in enumerate(sections, 1):
            logger.info(f"  スライド {i}/{len(sections)}: {section['title']}")
            html = self._generate_slide_html(section, i, len(sections))
            png_path = output_dir / f"slide_{i:03d}.png"
            html_slide_pairs.append((html, png_path))
            # レート制限対策：1スライドごとに待機（4096トークン × 8枚 = 余裕を持って）
            if i < len(sections):
                time.sleep(8)
            slide_data.append({
                "slide_num": i,
                "title": section["title"],
                "png_path": str(png_path),
                "script_fragment": section.get("script_fragment", ""),
            })

        # Step3: 一括レンダリング
        logger.info("スライドをレンダリング中...")
        self.renderer.render_batch(html_slide_pairs)

        logger.info(f"スライド生成完了: {len(slide_data)}枚 → {output_dir}")
        return slide_data

    def _parse_sections(self, script: str) -> list[dict]:
        prompt = SCRIPT_PARSER_PROMPT.format(script=script[:6000])
        raw = self._call_claude(prompt, max_tokens=3000)
        data = self._parse_json_response(raw)
        return data.get("sections", [])

    def _generate_slide_html(self, section: dict, slide_num: int, total: int) -> str:
        prompt = SLIDE_DESIGN_PROMPT.format(
            section_title=section["title"],
            section_content=section["content"],
            slide_num=slide_num,
            total_slides=total,
        )
        raw = self._call_claude(prompt, max_tokens=4096)

        # パターン1: ```html ... ``` (完全な形)
        match = re.search(r"```html\s*(.*?)\s*```", raw, re.DOTALL)
        if match:
            html = match.group(1).strip()
            if "<html" in html.lower():
                return html

        # パターン2: ```html から始まるが ``` で終わっていない（トークン切れ）
        match = re.search(r"```html\s*(<!DOCTYPE.*)", raw, re.DOTALL | re.IGNORECASE)
        if match:
            html = match.group(1).strip()
            # </html>がなければ補完
            if not re.search(r"</html>", html, re.IGNORECASE):
                html = html + "\n</body></html>"
            return html

        # パターン3: HTMLがそのまま出力（完全な形）
        html_match = re.search(r"(<!DOCTYPE.*?</html>)", raw, re.DOTALL | re.IGNORECASE)
        if html_match:
            return html_match.group(1).strip()

        # パターン4: <!DOCTYPE から始まるが途中で切れている
        html_match = re.search(r"(<!DOCTYPE.*)", raw, re.DOTALL | re.IGNORECASE)
        if html_match:
            html = html_match.group(1).strip()
            if not re.search(r"</html>", html, re.IGNORECASE):
                html = html + "\n</body></html>"
            return html

        logger.warning(f"スライド{slide_num}: HTML抽出失敗、フォールバック使用")
        return self._fallback_slide(section["title"], section["content"])

    def _fallback_slide(self, title: str, content: str) -> str:
        return f"""<!DOCTYPE html>
<html><head><style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ width: 1920px; height: 1080px; overflow: hidden;
  background: linear-gradient(135deg, #0a1628 0%, #1e3a5f 100%);
  display: flex; flex-direction: column; justify-content: center;
  align-items: center; font-family: system-ui, sans-serif; color: white; }}
h1 {{ font-size: 72px; font-weight: 800; color: #00b4d8; margin-bottom: 40px;
  text-align: center; line-height: 1.2; }}
p {{ font-size: 42px; color: #e0e0e0; text-align: center; max-width: 1400px;
  line-height: 1.6; }}
</style></head>
<body><h1>{title}</h1><p>{content}</p></body></html>"""
