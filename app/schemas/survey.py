from datetime import datetime

from pydantic import BaseModel, Field


class RoomMeasureItem(BaseModel):
    """单个房间测量数据"""
    name: str = Field(..., max_length=100)
    room_type: str = Field(default="bedroom")  # living_room, bedroom, kitchen, bathroom, study, balcony
    width: float = Field(..., gt=0)            # 宽度(米)
    length: float = Field(..., gt=0)           # 长度(米)
    area: float | None = None                  # 面积(自动计算)
    notes: str | None = None                   # 备注


class SurveyCreate(BaseModel):
    project_id: str
    name: str = Field(default="现场测量", max_length=200)
    surveyor: str | None = None
    method: str = Field(default="manual")        # manual | lidar | visual | photo | voice_guided
    scene_type: str = Field(default="indoor")     # indoor | outdoor | balcony
    wall_height: float = Field(default=2.8, ge=2.0, le=5.0)
    rooms: list[RoomMeasureItem] = Field(default_factory=list, min_length=1)
    scan_data: str | None = None                  # LiDAR/摄像头原始数据 JSON
    voice_transcript: str | None = None           # 语音引导对话记录
    device_info: str | None = None                # 设备信息 JSON
    notes: str | None = None


class SurveyUpdate(BaseModel):
    name: str | None = None
    surveyor: str | None = None
    method: str | None = None
    scene_type: str | None = None
    wall_height: float | None = None
    rooms: list[RoomMeasureItem] | None = None
    scan_data: str | None = None
    voice_transcript: str | None = None
    device_info: str | None = None
    status: str | None = None
    notes: str | None = None


class SurveyResponse(BaseModel):
    id: str
    project_id: str
    name: str
    surveyor: str | None
    method: str
    scene_type: str
    wall_height: float
    total_area: float
    rooms_data: str
    scan_data: str | None
    voice_transcript: str | None
    device_info: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SurveyListItem(BaseModel):
    id: str
    project_id: str
    name: str
    surveyor: str | None
    method: str
    scene_type: str
    total_area: float
    wall_height: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
