"""Skema request/response API."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class MuteRange(BaseModel):
    start: str = ""
    end: str = ""


class GenerateRequest(BaseModel):
    upload_id: str = ""
    episode: str = ""
    start: str = ""
    end: str = ""
    title: str = ""
    template: str = "default"
    fit: str = "cover"
    video_layout: str = "template_background"
    output_width: int = 1080
    output_height: int = 1920
    arc: str = ""
    notes: str = ""
    caption: bool = True
    frames: int = 0          # jumlah frame untuk caption AI; 0 = default server (CAPTION_FRAMES)
    replace_audio: bool = False
    music_upload_id: str = ""       # kosong + use_default_music=True -> pakai assets/audio/default_music.*
    use_default_music: bool = False
    mute_ranges: List[MuteRange] = []
    audio_only: bool = False   # True = "Ganti Backsound Saja": video asli dipakai penuh, tanpa template/trim/caption


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    size: int
    duration: float
    duration_text: str
    width: int
    height: int
    has_audio: bool


class AudioUploadResponse(BaseModel):
    upload_id: str
    filename: str
    size: int
    duration: float
    duration_text: str


class GenerateResponse(BaseModel):
    job_id: str
    status: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    stage: str = ""
    error: Optional[str] = None
    download_url: Optional[str] = None
    filename: Optional[str] = None
    caption_status: str = "off"          # off | pending | ready
    caption_source: Optional[str] = None  # ai | template
    caption_error: Optional[str] = None


class CaptionRequest(BaseModel):
    arc: Optional[str] = None
    notes: Optional[str] = None


class CaptionResponse(BaseModel):
    job_id: str
    status: str
    source: Optional[str] = None
    text: str = ""
    filename: str = ""
    error: Optional[str] = None
