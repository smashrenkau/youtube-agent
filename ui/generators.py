"""タイトル・台本・スライド生成の関数群。"""
import json
import logging
import re
from pathlib import Path

from agents.base_agent import BaseAgent
from ui.content_folder import ContentFolder

logger = logging.getLogger(__name__)

TITLE_GENERATION_PROMPT = '''あなたはYouTubeコンテンツの専門家です。
以下のブランド情報と参考動画をもとに、YouTube動画のタイトル候補を{num_titles}本生成してください。

## ブランド・商材情報
{context}

## YouTube参考動画（高再生数）
{youtube_results}

## タイトル生成ルール
- 30文字以内
- 検索されやすいキーワードを含む
- ターゲット（審査落ち・ブラックリスト経験者）が「自分のことだ」と思える
- 数字・具体性・共感のいずれかを含む
- 毎回異なる切り口で生成する

## 出力形式（JSONのみ）
{{
  "titles": [
    "タイトル1",
    "タイトル2"
  ]
}}

JSONのみ出力してください。
'''

SCRIPT_GENERATION_PROMPT = '''あなたは視聴者を惹きつけるYouTube台本のプロです。
以下の情報をもとに、動画台本を生成してください。

## ブランド・商材情報
{context}

## 動画タイトル
{title}

## 台本生成ルール
- 話し言葉（〜なんです、〜ですよね）
- 2500〜3500文字
- 必須訴求ポイント（総量規制対象外・審査なし・2年所有化・今すぐ生活を整える）を全て含める
- 自然な流れでサービスを紹介する
- 「まず知るだけでいい」など、ハードルの低い行動で締める

台本のみ出力してください（説明文不要）。
'''


class _SimpleAgent(BaseAgent):
    """UI用のシンプルなエージェント（runメソッドは使わない）。"""

    def run(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError


def generate_titles(folder: ContentFolder, num_titles: int) -> list[str]:
    """フォルダのコンテキストとYouTube検索結果からタイトルを生成する。"""
    from youtube.searcher import YouTubeSearcher
    from config.settings import get_settings

    settings = get_settings()
    context = folder.get_context()

    # YouTube検索
    youtube_results = "（YouTube検索結果なし）"
    if settings.youtube_data_api_key:
        try:
            searcher = YouTubeSearcher(settings.youtube_data_api_key)
            videos = searcher.search_top_videos(folder.keywords[:3], max_per_keyword=3)
            youtube_results = searcher.format_for_prompt(videos, top_n=6)
        except Exception as e:
            logger.warning(f"YouTube検索失敗: {e}")

    prompt = TITLE_GENERATION_PROMPT.format(
        num_titles=num_titles,
        context=context[:4000],
        youtube_results=youtube_results,
    )

    agent = _SimpleAgent()
    raw = agent._call_claude(prompt, max_tokens=2000)

    # JSON抽出
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        data = json.loads(match.group())
        return data.get("titles", [])

    # フォールバック：行ごとに分割
    lines = [line.strip().lstrip("0123456789.-） ").strip()
             for line in raw.splitlines() if line.strip()]
    return [l for l in lines if len(l) > 5][:num_titles]


def generate_script(title: str, folder: ContentFolder) -> str:
    """タイトルとフォルダコンテキストから台本を生成する。"""
    context = folder.get_context()
    prompt = SCRIPT_GENERATION_PROMPT.format(
        context=context[:4000],
        title=title,
    )
    agent = _SimpleAgent()
    return agent._call_claude(prompt, max_tokens=4096)


def generate_slides(script: str, title: str, folder: ContentFolder | None = None) -> list[dict]:
    """台本からスライドを生成してPNGパスのリストを返す。"""
    from slides.slide_agent import SlideGeneratorAgent

    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:40]
    output_dir = Path("storage/slides") / safe_title
    output_dir.mkdir(parents=True, exist_ok=True)

    # フォルダのコンテキストからスライド仕様書を抽出
    slide_spec = None
    if folder:
        context = folder.get_context()
        import re
        match = re.search(r"##\s*スライド仕様書\n(.*?)(?=\n##\s|\Z)", context, re.DOTALL)
        if match:
            slide_spec = match.group(1).strip()
            logger.info("Notionのスライド仕様書を使用")

    agent = SlideGeneratorAgent()
    return agent.generate_slides(script, output_dir, slide_spec=slide_spec)
