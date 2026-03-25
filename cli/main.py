"""CLIエントリポイント（Typer）。"""
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="youtube-agent",
    help="YouTube動画全自動化AIエージェントシステム",
    add_completion=False,
)
console = Console()


def _setup_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # httpx等の過剰なログを抑制
    for noisy in ["httpx", "httpcore", "openai", "anthropic"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _build_youtube_searcher():  # type: ignore[no-untyped-def]
    """YouTubeSearcherを初期化して返す。APIキー未設定なら None を返す。"""
    from config.settings import get_settings
    from youtube.searcher import YouTubeSearcher

    settings = get_settings()
    api_key = settings.youtube_data_api_key
    if not api_key:
        return None
    return YouTubeSearcher(api_key=api_key)


def _build_retriever(rebuild: bool = False):  # type: ignore[no-untyped-def]
    """RAGリトリーバーを初期化して返す。"""
    from config.settings import get_settings
    from rag.index_builder import IndexBuilder
    from rag.notion_loader import NotionLoader
    from rag.retriever import Retriever

    settings = get_settings()
    loader = NotionLoader(
        api_key=settings.notion_api_key.get_secret_value(),
        database_id=settings.notion_database_id,
    )
    builder = IndexBuilder(
        notion_loader=loader,
        cache_dir=settings.rag_cache_dir,
        refresh_hours=settings.rag_index_refresh_hours,
    )
    index = builder.get_index(force_rebuild=rebuild)
    return Retriever(index)


# ============================================================
# youtube-agent run  — 全パイプライン実行
# ============================================================
@app.command()
def run(
    purpose: Annotated[str, typer.Option("--purpose", "-p", help="動画の目的")],
    genre: Annotated[str, typer.Option("--genre", "-g", help="ジャンル")],
    chars: Annotated[int, typer.Option("--chars", "-c", help="台本の目標文字数")] = 3000,
    style: Annotated[str, typer.Option("--style", help="話し方・スタイルの補足")] = "",
    template: Annotated[str, typer.Option("--template", help="動画テンプレート名")] = "default_template",
    keywords: Annotated[Optional[str], typer.Option("--keywords", "-k", help="YouTube検索キーワード（カンマ区切り）")] = None,
    auto: Annotated[bool, typer.Option("--auto", help="確認ステップをスキップ")] = False,
    no_rag: Annotated[bool, typer.Option("--no-rag", help="RAGを使わない（Notion不要）")] = False,
    no_yt_search: Annotated[bool, typer.Option("--no-yt-search", help="YouTube検索をスキップ")] = False,
    log_level: Annotated[str, typer.Option("--log-level")] = "INFO",
) -> None:
    """テーマ選定→台本→動画→YouTube投稿の全工程を実行。"""
    from config.settings import get_settings
    from models.schemas import PipelineRequest
    from pipelines.full_pipeline import FullPipeline

    _setup_logging(log_level)
    settings = get_settings()

    retriever = None if no_rag else _build_retriever()
    youtube_searcher = None if no_yt_search else _build_youtube_searcher()

    keyword_list = [k.strip() for k in keywords.split(",")] if keywords else []

    pipeline = FullPipeline(retriever=retriever, youtube_searcher=youtube_searcher)
    request = PipelineRequest(
        purpose=purpose,
        genre=genre,
        keywords=keyword_list,
        target_chars=chars,
        style_notes=style,
        template_name=template,
        auto_approve=auto,
    )

    try:
        result = pipeline.run(request)
        if result.upload:
            console.print(f"\n[bold green]投稿URL: {result.upload.video_url}[/bold green]")
    except SystemExit:
        pass
    except Exception as e:
        console.print(f"[bold red]エラー: {e}[/bold red]")
        logging.exception("パイプラインエラー")
        raise typer.Exit(1)


# ============================================================
# youtube-agent theme  — テーマ選定のみ
# ============================================================
@app.command()
def theme(
    purpose: Annotated[str, typer.Option("--purpose", "-p", help="動画の目的")],
    genre: Annotated[str, typer.Option("--genre", "-g", help="ジャンル")],
    keywords: Annotated[Optional[str], typer.Option("--keywords", "-k", help="YouTube検索キーワード（カンマ区切り）")] = None,
    count: Annotated[int, typer.Option("--count", "-n", help="候補数")] = 5,
    no_rag: Annotated[bool, typer.Option("--no-rag")] = False,
    no_yt_search: Annotated[bool, typer.Option("--no-yt-search")] = False,
    log_level: Annotated[str, typer.Option("--log-level")] = "INFO",
) -> None:
    """タイトル候補を生成して表示。"""
    from agents.theme_selector import ThemeSelectorAgent
    from models.schemas import ThemeRequest
    from rich.table import Table

    _setup_logging(log_level)
    retriever = None if no_rag else _build_retriever()
    youtube_searcher = None if no_yt_search else _build_youtube_searcher()
    keyword_list = [k.strip() for k in keywords.split(",")] if keywords else []

    agent = ThemeSelectorAgent(retriever, youtube_searcher)
    result = agent.run(ThemeRequest(purpose=purpose, genre=genre, keywords=keyword_list, count=count))

    # 参考動画を表示
    if result.reference_videos:
        console.print(f"\n[bold]参考にした高再生数動画 (Top {min(5, len(result.reference_videos))}件)[/bold]")
        ref_table = Table(show_lines=True)
        ref_table.add_column("再生数", style="yellow", justify="right")
        ref_table.add_column("タイトル", style="white")
        ref_table.add_column("チャンネル", style="dim")
        for v in result.reference_videos[:5]:
            ref_table.add_row(f"{v.view_count:,}", v.title, v.channel)
        console.print(ref_table)

    # タイトル候補を表示
    console.print(f"\n[bold]タイトル候補[/bold]")
    for i, c in enumerate(result.candidates, 1):
        ctr_color = {"High": "green", "Medium": "yellow", "Low": "red"}.get(c.estimated_ctr, "white")
        console.print(f"\n[cyan]{i}.[/cyan] [bold]{c.title}[/bold]")
        console.print(f"   フック: {c.hook_type} | CTR予測: [{ctr_color}]{c.estimated_ctr}[/{ctr_color}]")
        console.print(f"   理由: [dim]{c.reasoning}[/dim]")


# ============================================================
# youtube-agent script  — 台本作成のみ
# ============================================================
@app.command()
def script(
    title: Annotated[str, typer.Option("--title", "-t", help="動画タイトル")],
    chars: Annotated[int, typer.Option("--chars", "-c", help="目標文字数")] = 3000,
    style: Annotated[str, typer.Option("--style", help="スタイル補足")] = "",
    no_rag: Annotated[bool, typer.Option("--no-rag")] = False,
    log_level: Annotated[str, typer.Option("--log-level")] = "INFO",
) -> None:
    """台本を生成して保存。"""
    from agents.script_writer import ScriptWriterAgent
    from models.schemas import ScriptRequest

    _setup_logging(log_level)
    retriever = None if no_rag else _build_retriever()
    agent = ScriptWriterAgent(retriever)
    result = agent.run(ScriptRequest(title=title, target_chars=chars, style_notes=style))

    console.print(f"\n[bold green]台本完成[/bold green]")
    console.print(f"文字数: {result.char_count} | レビュー: {result.revision_count}回")
    console.print(f"保存先: {result.output_path}")


# ============================================================
# youtube-agent video  — 動画生成のみ
# ============================================================
@app.command()
def video(
    script_path: Annotated[str, typer.Option("--script-path", "-s", help="台本ファイルパス")],
    title: Annotated[str, typer.Option("--title", "-t", help="動画タイトル")],
    template: Annotated[str, typer.Option("--template")] = "default_template",
    log_level: Annotated[str, typer.Option("--log-level")] = "INFO",
) -> None:
    """台本ファイルから動画を生成。"""
    from agents.video_generator import VideoGeneratorAgent
    from models.schemas import VideoRequest

    _setup_logging(log_level)
    script_text = Path(script_path).read_text(encoding="utf-8")
    agent = VideoGeneratorAgent()
    result = agent.run(VideoRequest(script=script_text, title=title, template_name=template))

    console.print(f"\n[bold green]動画完成[/bold green]")
    console.print(f"動画: {result.video_path}")
    console.print(f"長さ: {result.duration_sec:.1f}秒")


# ============================================================
# youtube-agent upload  — YouTube投稿のみ
# ============================================================
@app.command()
def upload(
    video_path: Annotated[str, typer.Option("--video-path", "-v", help="動画ファイルパス")],
    title: Annotated[str, typer.Option("--title", "-t", help="動画タイトル")],
    description: Annotated[str, typer.Option("--description", "-d", help="説明文")] = "",
    thumbnail: Annotated[Optional[str], typer.Option("--thumbnail")] = None,
    privacy: Annotated[str, typer.Option("--privacy")] = "private",
    log_level: Annotated[str, typer.Option("--log-level")] = "INFO",
) -> None:
    """動画ファイルをYouTubeに投稿。"""
    from agents.youtube_uploader import YouTubeUploaderAgent
    from models.schemas import UploadRequest

    _setup_logging(log_level)
    agent = YouTubeUploaderAgent()
    result = agent.run(
        UploadRequest(
            video_path=video_path,
            title=title,
            description=description,
            thumbnail_path=thumbnail,
            privacy=privacy,  # type: ignore[arg-type]
        )
    )

    console.print(f"\n[bold green]投稿完了[/bold green]")
    console.print(f"URL: {result.video_url}")


# ============================================================
# youtube-agent index  — RAGインデックス再構築
# ============================================================
@app.command()
def index(
    rebuild: Annotated[bool, typer.Option("--rebuild", "-r", help="強制再構築")] = False,
    log_level: Annotated[str, typer.Option("--log-level")] = "INFO",
) -> None:
    """NotionからRAGインデックスを構築（または再構築）。"""
    _setup_logging(log_level)
    console.print("RAGインデックスを構築中...")
    _build_retriever(rebuild=rebuild)
    console.print("[bold green]インデックス構築完了[/bold green]")


if __name__ == "__main__":
    app()
