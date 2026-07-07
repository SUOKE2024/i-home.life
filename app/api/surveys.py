from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_user
from app.schemas.survey import SurveyCreate, SurveyUpdate, SurveyResponse, SurveyListItem
from app.services import survey_service

router = APIRouter(prefix="/surveys", tags=["surveys"])


def _current_user(user=Depends(get_current_user)):
    return user


@router.post("", response_model=SurveyResponse, status_code=status.HTTP_201_CREATED)
async def create_survey(body: SurveyCreate, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    data = body.model_dump()
    rooms = data.pop("rooms", [])
    rooms_data = [r.model_dump() if hasattr(r, "model_dump") else r for r in rooms]
    return await survey_service.create_survey(db, data, rooms_data)


@router.get("/project/{project_id}", response_model=list[SurveyListItem])
async def list_surveys(project_id: str, db: AsyncSession = Depends(get_db)):
    return await survey_service.get_surveys_by_project(db, project_id)


@router.get("/device-check", response_model=dict)
async def device_check():
    """检测设备可用硬件能力 — LiDAR/摄像头/语音等"""
    return {
        "available_sensors": {
            "lidar": {
                "supported_platforms": ["iOS 14+", "iPadOS 14+", "macOS (ARKit)"],
                "api": "ARKit SceneReconstruction / RoomPlan",
                "requires_device": "iPhone 12 Pro / iPad Pro 2020+",
                "fallback": "手动测量 + 视觉辅助"
            },
            "camera": {
                "supported_platforms": ["all"],
                "api": "Web MediaDevices / Flutter camera plugin",
                "capabilities": ["photo_capture", "video_stream", "qr_scan", "photogrammetry"],
                "resolution": "auto"
            },
            "voice": {
                "supported_platforms": ["all"],
                "api": "Web Speech API / Whisper",
                "capabilities": ["speech_to_text", "voice_command", "measurement_guidance"],
                "languages": ["zh-CN", "en-US"]
            },
            "accelerometer": {
                "supported_platforms": ["iOS", "Android", "HarmonyOS"],
                "api": "DeviceOrientation API",
                "capabilities": ["level_detection", "angle_measurement"]
            }
        },
        "recommended_workflow": {
            "lidar_available": [
                "1. 打开 AR 扫描 → 2. 沿房间边界行走 → 3. 自动生成户型 → 4. 手动调整标注",
                "预计耗时: 3 分钟 / 100㎡"
            ],
            "no_lidar": [
                "1. 选择手动测量或摄像头辅助 → 2. 逐个输入房间尺寸 → 3. 语音说出尺寸 → 4. 确认保存",
                "预计耗时: 10 分钟 / 100㎡"
            ],
            "voice_guided": [
                "说：「开始测量」→ AI 引导说出每个房间的名称和尺寸 → 自动计算总面积",
                "支持语音命令: 测量 / 下一个 / 完成 / 修改房间名称 / 删除房间"
            ]
        }
    }


@router.get("/{survey_id}", response_model=SurveyResponse)
async def get_survey(survey_id: str, db: AsyncSession = Depends(get_db)):
    s = await survey_service.get_survey(db, survey_id)
    if not s:
        raise HTTPException(status_code=404, detail="测量记录不存在")
    return s


@router.put("/{survey_id}", response_model=SurveyResponse)
async def update_survey(survey_id: str, body: SurveyUpdate, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    s = await survey_service.get_survey(db, survey_id)
    if not s:
        raise HTTPException(status_code=404, detail="测量记录不存在")
    data = body.model_dump(exclude_none=True)
    return await survey_service.update_survey(db, s, data)


@router.delete("/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_survey(survey_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    s = await survey_service.get_survey(db, survey_id)
    if not s:
        raise HTTPException(status_code=404, detail="测量记录不存在")
    await survey_service.delete_survey(db, s)


@router.post("/{survey_id}/apply", response_model=dict)
async def apply_survey(survey_id: str, db: AsyncSession = Depends(get_db), user=Depends(_current_user)):
    """将测量数据应用到项目楼层房间 — 一键生成户型"""
    s = await survey_service.get_survey(db, survey_id)
    if not s:
        raise HTTPException(status_code=404, detail="测量记录不存在")
    return await survey_service.apply_survey_to_project(db, s)
