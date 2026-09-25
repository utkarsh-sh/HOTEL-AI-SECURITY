from pydantic import BaseModel, Field


class ZoneCreateRequest(BaseModel):
    zone_id: str
    camera_id: str
    name: str
    type: str
    points: list[list[float]] = Field(min_length=3)


class ZoneUpdateRequest(BaseModel):
    camera_id: str
    name: str
    type: str
    points: list[list[float]] = Field(min_length=3)
