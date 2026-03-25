from typing import Literal

from pydantic import BaseModel, Field


# ===================== テーマ選定 =====================

class ThemeRequest(BaseModel):
    purpose: str = Field(..., description="動画の目的（例: 副業初心者に向けてノウハウを伝える）")
    genre: str = Field(..., description="ジャンル（例: ノウハウ系、Vlog、解説）")
    keywords: list[str] = Field(default_factory=list, description="YouTube検索キーワード（複数可）")
    count: int = Field(5, ge=1, le=10, description="タイトル候補数")


class YouTubeVideoInfo(BaseModel):
    title: str
    channel: str
    view_count: int
    video_id: str
    url: str
    published_at: str


class TitleCandidate(BaseModel):
    title: str
    hook_type: str = Field(..., description="数字系・疑問系・共感系 など")
    estimated_ctr: Literal["High", "Medium", "Low"]
    reasoning: str
    source_video_id: str | None = None  # 参考にした動画ID


class ThemeResult(BaseModel):
    candidates: list[TitleCandidate]
    reference_videos: list[YouTubeVideoInfo] = Field(default_factory=list)
    selected_title: str | None = None


# ===================== 台本作成 =====================

class ScriptRequest(BaseModel):
    title: str
    target_chars: int = Field(3000, ge=500, le=10000, description="台本の目標文字数")
    style_notes: str = Field("", description="話し方・スタイルの補足指示")


class ReviewScore(BaseModel):
    hook_score: int = Field(..., ge=1, le=5, description="冒頭フックの評価")
    style_score: int = Field(..., ge=1, le=5, description="話し方一致度")
    length_score: int = Field(..., ge=1, le=5, description="文字数適切さ")
    structure_score: int = Field(..., ge=1, le=5, description="構成の明確さ")
    total: int
    feedback: str
    approved: bool


class ScriptResult(BaseModel):
    title: str
    script: str
    char_count: int
    revision_count: int
    review_history: list[ReviewScore]
    output_path: str | None = None


# ===================== 動画生成 =====================

class VideoRequest(BaseModel):
    script: str
    title: str
    template_name: str = "default_template"


class VideoResult(BaseModel):
    video_path: str
    audio_path: str
    thumbnail_path: str
    duration_sec: float


# ===================== YouTube投稿 =====================

class UploadRequest(BaseModel):
    video_path: str
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    thumbnail_path: str | None = None
    privacy: Literal["private", "unlisted", "public"] = "private"


class UploadResult(BaseModel):
    video_id: str
    video_url: str
    status: str


# ===================== パイプライン =====================

class PipelineRequest(BaseModel):
    purpose: str
    genre: str
    keywords: list[str] = Field(default_factory=list, description="YouTube検索キーワード")
    target_chars: int = 3000
    style_notes: str = ""
    template_name: str = "default_template"
    auto_approve: bool = Field(False, description="ユーザー確認ステップをスキップ")


class PipelineResult(BaseModel):
    theme: ThemeResult
    script: ScriptResult
    video: VideoResult
    upload: UploadResult | None = None
