"""4エージェントをオーケストレートするメインパイプライン。"""
import json
import logging
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from agents.theme_selector import ThemeSelectorAgent
from agents.script_writer import ScriptWriterAgent
from agents.video_generator import VideoGeneratorAgent
from agents.youtube_uploader import YouTubeUploaderAgent
from config.settings import get_settings
from notion.reporter import NotionReporter
from models.schemas import (
    PipelineRequest,
    PipelineResult,
    ScriptRequest,
    ThemeRequest,
    UploadRequest,
    VideoRequest,
)

logger = logging.getLogger(__name__)
console = Console()


class FullPipeline:
    """テーマ選定→台本→動画→YouTube投稿の全工程を実行するオーケストレーター。"""

    def __init__(self, retriever=None, youtube_searcher=None) -> None:  # type: ignore[no-untyped-def]
        self.retriever = retriever
        self.theme_agent = ThemeSelectorAgent(retriever, youtube_searcher)
        self.script_agent = ScriptWriterAgent(retriever)
        settings = get_settings()
        self.reporter: NotionReporter | None = None
        if settings.notion_log_database_id:
            self.reporter = NotionReporter(
                api_key=settings.notion_api_key.get_secret_value(),
                log_database_id=settings.notion_log_database_id,
            )
        self.video_agent = VideoGeneratorAgent(retriever=retriever)
        self.upload_agent = YouTubeUploaderAgent(retriever)

    def run(self, request: PipelineRequest) -> PipelineResult:
        settings = get_settings()
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        state_path = log_dir / f"pipeline_{run_id}.json"
        state: dict = {"run_id": run_id, "request": request.model_dump(), "steps": {}}

        console.print(f"\n[bold cyan]YouTube Agent パイプライン開始[/bold cyan] (ID: {run_id})")

        # ============================================================
        # Step 1: テーマ選定
        # ============================================================
        console.print("\n[bold]Step 1: テーマ選定[/bold]")
        theme_result = self.theme_agent.run(
            ThemeRequest(
                purpose=request.purpose,
                genre=request.genre,
                keywords=request.keywords,
            )
        )
        state["steps"]["theme"] = theme_result.model_dump()
        self._save_state(state_path, state)

        # タイトル候補を表示してユーザーに選択させる
        selected_title = self._select_title(
            theme_result.candidates, request.auto_approve, theme_result.reference_videos
        )
        theme_result.selected_title = selected_title
        state["steps"]["theme"]["selected_title"] = selected_title
        self._save_state(state_path, state)

        # ============================================================
        # Step 2: 台本作成
        # ============================================================
        console.print("\n[bold]Step 2: 台本作成[/bold]")
        script_result = self.script_agent.run(
            ScriptRequest(
                title=selected_title,
                target_chars=request.target_chars,
                style_notes=request.style_notes,
            )
        )
        state["steps"]["script"] = {
            "title": script_result.title,
            "char_count": script_result.char_count,
            "revision_count": script_result.revision_count,
            "output_path": script_result.output_path,
        }
        self._save_state(state_path, state)

        console.print(
            f"  台本完成: {script_result.char_count}文字 "
            f"(レビュー{script_result.revision_count}回)"
        )
        if script_result.output_path:
            console.print(f"  保存先: [dim]{script_result.output_path}[/dim]")

        # ユーザー確認（台本レビュー）
        if not request.auto_approve:
            self._preview_script(script_result.script)
            if not Confirm.ask("この台本で動画を生成しますか？"):
                console.print("[yellow]パイプラインを中断しました。[/yellow]")
                raise SystemExit(0)

        # ============================================================
        # Step 3: 動画生成
        # ============================================================
        console.print("\n[bold]Step 3: 動画生成[/bold]")
        video_result = self.video_agent.run(
            VideoRequest(
                script=script_result.script,
                title=selected_title,
                template_name=request.template_name,
            )
        )
        state["steps"]["video"] = video_result.model_dump()
        self._save_state(state_path, state)

        console.print(f"  動画完成: {video_result.duration_sec:.1f}秒")
        console.print(f"  保存先: [dim]{video_result.video_path}[/dim]")

        # ユーザー確認（YouTube投稿）
        upload_result = None
        if not request.auto_approve:
            if not Confirm.ask("YouTubeに投稿しますか？"):
                console.print("[yellow]投稿をスキップしました。[/yellow]")
            else:
                upload_result = self._do_upload(
                    video_result, script_result, selected_title, settings
                )
        else:
            upload_result = self._do_upload(
                video_result, script_result, selected_title, settings
            )

        if upload_result:
            state["steps"]["upload"] = upload_result.model_dump()
            self._save_state(state_path, state)

        # Notionに全結果を保存
        if self.reporter:
            try:
                notion_url = self.reporter.save_pipeline_result(
                    title=selected_title,
                    theme=theme_result,
                    script=script_result,
                    video=video_result,
                    upload=upload_result,
                )
                console.print(f"  Notion保存: [link]{notion_url}[/link]")
            except Exception as e:
                logger.warning(f"Notion保存失敗: {e}")

        # 完了
        console.print(f"\n[bold green]✓ パイプライン完了[/bold green] (ログ: {state_path})")

        return PipelineResult(
            theme=theme_result,
            script=script_result,
            video=video_result,
            upload=upload_result,
        )

    def _select_title(self, candidates, auto_approve: bool, reference_videos=None) -> str:  # type: ignore[no-untyped-def]
        # 参考動画があれば表示
        if reference_videos:
            ref_table = Table(title=f"参考にした高再生数動画 (Top {min(5, len(reference_videos))}件)", show_lines=True)
            ref_table.add_column("再生数", style="yellow", justify="right")
            ref_table.add_column("タイトル", style="white")
            ref_table.add_column("チャンネル", style="dim")
            for v in reference_videos[:5]:
                ref_table.add_row(f"{v.view_count:,}", v.title, v.channel)
            console.print(ref_table)

        table = Table(title="タイトル候補", show_lines=True)
        table.add_column("No.", style="cyan", width=4)
        table.add_column("タイトル", style="white")
        table.add_column("フック", style="dim")
        table.add_column("CTR予測", style="green")

        for i, c in enumerate(candidates, 1):
            ctr_color = {"High": "green", "Medium": "yellow", "Low": "red"}.get(
                c.estimated_ctr, "white"
            )
            table.add_row(
                str(i),
                c.title,
                c.hook_type,
                f"[{ctr_color}]{c.estimated_ctr}[/{ctr_color}]",
            )

        console.print(table)

        if auto_approve:
            # High CTRの最初のものを自動選択
            for c in candidates:
                if c.estimated_ctr == "High":
                    console.print(f"  自動選択: {c.title}")
                    return c.title
            return candidates[0].title

        choice = Prompt.ask(
            "タイトルを選択してください",
            choices=[str(i) for i in range(1, len(candidates) + 1)],
        )
        return candidates[int(choice) - 1].title

    def _preview_script(self, script: str) -> None:
        console.print("\n[bold]--- 台本プレビュー（冒頭500文字）---[/bold]")
        console.print(script[:500] + ("..." if len(script) > 500 else ""))
        console.print("[bold]--- プレビュー終了 ---[/bold]\n")

    def _do_upload(self, video_result, script_result, title, settings):  # type: ignore[no-untyped-def]
        console.print("\n[bold]Step 4: YouTube投稿[/bold]")
        description = self.upload_agent.generate_description(title, script_result.script)
        result = self.upload_agent.run(
            UploadRequest(
                video_path=video_result.video_path,
                title=title,
                description=description,
                tags=[],
                thumbnail_path=video_result.thumbnail_path,
                privacy=settings.youtube_default_privacy,
            )
        )
        console.print(f"  投稿完了: [link]{result.video_url}[/link]")
        return result

    def _save_state(self, path: Path, state: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)
