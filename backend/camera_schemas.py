from typing import Literal

from pydantic import BaseModel, Field


class CameraReconnectConfig(BaseModel):
    max_attempts: int = Field(default=3, ge=0)
    delay_seconds: float = Field(default=1.0, ge=0)


class CameraCreateRequest(BaseModel):
    camera_id: str
    name: str
    location: str
    source_type: Literal["file", "rtsp"]
    source: str
    ai_fps: float = Field(gt=0)
    reconnect: CameraReconnectConfig = Field(
        default_factory=CameraReconnectConfig
    )


class CameraUpdateRequest(BaseModel):
    name: str
    location: str
    source_type: Literal["file", "rtsp"]
    source: str
    ai_fps: float = Field(gt=0)
    reconnect: CameraReconnectConfig = Field(
        default_factory=CameraReconnectConfig
    )
