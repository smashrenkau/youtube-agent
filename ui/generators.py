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

## 既に作成済みのタイトル（重複禁止）
{existing_titles}

## タイトル生成ルール
- 30文字以内
- 検索されやすいキーワードを含む
- ターゲット（審査落ち・ブラックリスト経験者）が「自分のことだ」と思える
- 数字・具体性・共感のいずれかを含む
- 毎回異なる切り口で生成する
- 「既に作成済みのタイトル」と同じ・似たタイトルは生成しない

## 出力形式（JSONのみ）
{{
  "titles": [
    "タイトル1",
    "タイトル2"
  ]
}}

JSONのみ出力してください。
'''

SHORT_TITLE_GENERATION_PROMPT = '''あなたはYouTube Shortsコンテンツの専門家です。
以下のブランド情報をもとに、YouTube Shortsのタイトル候補を{num_titles}本生成してください。

## ブランド・商材情報
{context}

## 既に作成済みのタイトル（重複禁止）
{existing_titles}

## タイトル生成ルール（ショート専用）
- 20文字以内（ショートは短く！）
- 検索されやすいキーワードを含む
- ターゲット（審査落ち・ブラックリスト経験者）が「自分のことだ」と思える
- 数字・具体性・共感のいずれかを含む
- 毎回異なる切り口で生成する
- 「既に作成済みのタイトル」と同じ・似たタイトルは生成しない

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

SHORT_SCRIPT_GENERATION_PROMPT = '''あなたはYouTube Shorts台本のプロです。
以下の情報をもとに、45秒以内のショート動画台本を生成してください。

## ブランド・商材情報
{context}

## 動画タイトル
{title}

## 台本生成ルール（ショート専用）
- 合計150〜200文字（厳守）
- 構成：①フック(5〜8秒) → ②解決策1〜2点(30秒) → ③CTA(5〜7秒)
- 話し言葉（〜なんです、〜ですよ）
- 一文10〜15文字以内
- Renkauへの言及は自然に入る場合のみ（無理に入れない）
- 不安を過度に煽る表現・「絶対」「必ず」などの断言は禁止

台本のみ出力してください（説明文不要）。
'''


class _SimpleAgent(BaseAgent):
    """UI用のシンプルなエージェント（runメソッドは使わない）。"""

    def run(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError


def _get_storage(folder: ContentFolder, video_type: str = "long"):
    """LocalStorageインスタンスを返す。保存先はフォルダ内の「生成物」ディレクトリ。"""
    from storage.local_storage import LocalStorage
    return LocalStorage(base_dir=folder.get_generated_dir(video_type))


def get_existing_titles(folder: ContentFolder, video_type: str = "long") -> list[str]:
    """ローカルに保存済みのタイトル一覧を返す（フォルダ・video_typeごとに独立管理）。"""
    try:
        return _get_storage(folder, video_type).get_existing_titles()
    except Exception as e:
        logger.warning(f"既存タイトル取得失敗: {e}")
        return []


def generate_titles(
    folder: ContentFolder, num_titles: int, video_type: str = "long"
) -> tuple[list[str], list[dict]]:
    """フォルダのコンテキストとYouTube検索結果からタイトルを生成する。

    Returns:
        (titles, reference_videos) のタプル。
        reference_videos は {title, url, view_count, channel} のリスト。
    """
    from youtube.searcher import YouTubeSearcher
    from config.settings import get_settings

    settings = get_settings()
    context = folder.get_context()

    reference_videos: list[dict] = []
    youtube_results = "（YouTube検索結果なし）"
    if settings.youtube_data_api_key:
        try:
            searcher = YouTubeSearcher(settings.youtube_data_api_key)
            videos = searcher.search_top_videos(folder.keywords[:3], max_per_keyword=3)
            reference_videos = [
                {"title": v.title, "url": v.url, "view_count": v.view_count, "channel": v.channel}
                for v in videos[:6]
            ]
            youtube_results = searcher.format_for_prompt(videos, top_n=6)
        except Exception as e:
            logger.warning(f"YouTube検索失敗: {e}")

    # 既存タイトルを取得（重複防止・フォルダ・video_typeごと独立）
    existing = get_existing_titles(folder, video_type=video_type)
    existing_titles_str = "\n".join(f"- {t}" for t in existing) if existing else "（なし）"

    # video_typeに応じてプロンプトを切り替え
    if video_type == "short":
        prompt = SHORT_TITLE_GENERATION_PROMPT.format(
            num_titles=num_titles,
            context=context[:4000],
            existing_titles=existing_titles_str,
        )
    else:
        prompt = TITLE_GENERATION_PROMPT.format(
            num_titles=num_titles,
            context=context[:4000],
            youtube_results=youtube_results,
            existing_titles=existing_titles_str,
        )

    agent = _SimpleAgent()
    raw = agent._call_claude(prompt, max_tokens=2000)

    # JSON抽出
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        data = json.loads(match.group())
        titles = data.get("titles", [])
    else:
        # フォールバック：行ごとに分割
        lines = [line.strip().lstrip("0123456789.-） ").strip()
                 for line in raw.splitlines() if line.strip()]
        titles = [l for l in lines if len(l) > 5][:num_titles]

    return titles, reference_videos


def save_titles(
    titles: list[str],
    folder: ContentFolder,
    video_type: str = "long",
    reference_videos: list[dict] | None = None,
) -> dict[str, str]:
    """タイトルをローカルに保存し {title: slug} を返す。参照動画も保存する。"""
    storage = _get_storage(folder, video_type)
    result = {}
    for title in titles:
        try:
            slug = storage.save_title(title)
            result[title] = slug
            if reference_videos:
                storage.save_reference_videos(slug, reference_videos)
        except Exception as e:
            logger.warning(f"タイトル保存失敗 ({title}): {e}")
    return result


def generate_script(title: str, folder: ContentFolder, video_type: str = "long") -> str:
    """タイトルとフォルダコンテキストから台本を生成する。"""
    context = folder.get_context()
    if video_type == "short":
        prompt = SHORT_SCRIPT_GENERATION_PROMPT.format(
            context=context[:4000],
            title=title,
        )
        max_tokens = 1024
    else:
        prompt = SCRIPT_GENERATION_PROMPT.format(
            context=context[:4000],
            title=title,
        )
        max_tokens = 4096
    agent = _SimpleAgent()
    return agent._call_claude(prompt, max_tokens=max_tokens)


def save_script(title: str, script: str, title_slugs: dict[str, str], folder: ContentFolder, video_type: str = "long") -> None:
    """台本をローカルに保存する。"""
    slug = title_slugs.get(title)
    if not slug:
        return
    try:
        _get_storage(folder, video_type).save_script(slug, script)
    except Exception as e:
        logger.warning(f"台本保存失敗 ({title}): {e}")


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
        match = re.search(r"##\s*スライド仕様書\n(.*?)(?=\n##\s|\Z)", context, re.DOTALL)
        if match:
            slide_spec = match.group(1).strip()
            logger.info("Notionのスライド仕様書を使用")

    agent = SlideGeneratorAgent()
    return agent.generate_slides(script, output_dir, slide_spec=slide_spec)


def save_slides(title: str, slides: list[dict], title_slugs: dict[str, str], folder: ContentFolder, video_type: str = "long") -> None:
    """スライド情報をローカルに保存する。"""
    slug = title_slugs.get(title)
    if not slug:
        return
    try:
        _get_storage(folder, video_type).save_slides(slug, slides)
    except Exception as e:
        logger.warning(f"スライド保存失敗 ({title}): {e}")
