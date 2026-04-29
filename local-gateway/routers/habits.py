"""
习惯养成路由
POST   /api/habits — 创建习惯
GET    /api/habits — 习惯列表
GET    /api/habits/{habit_id} — 习惯详情
POST   /api/habits/{habit_id}/checkin — 习惯打卡
GET    /api/habits/{habit_id}/stats — 习惯统计
DELETE /api/habits/{habit_id} — 删除习惯
"""
from fastapi import APIRouter

from models.schemas import BaseModel, Field
from services import task_service

router = APIRouter(prefix="/habits", tags=["habits"])


class HabitCreateRequest(BaseModel):
    name: str = Field(..., description="习惯名称")
    description: str = Field("", description="习惯描述")
    frequency: str = Field("daily", description="频率: daily/weekly/monthly")
    target_count: int = Field(1, ge=1, description="目标次数")
    reminder_time: str = Field(None, description="提醒时间 (HH:MM)")
    color: str = Field("#27ae60", description="习惯颜色")


class CheckinRequest(BaseModel):
    count: int = Field(1, ge=1, description="打卡次数")
    note: str = Field("", description="打卡备注")


@router.post("/")
async def create_habit(request: HabitCreateRequest):
    """创建习惯"""
    result = await task_service.create_habit(
        name=request.name,
        description=request.description,
        frequency=request.frequency,
        target_count=request.target_count,
        reminder_time=request.reminder_time,
        color=request.color,
    )
    return result


@router.get("/")
async def list_habits():
    """获取所有习惯"""
    habits = await task_service.get_all_habits()
    return {"status": "success", "habits": habits}


@router.get("/{habit_id}")
async def get_habit(habit_id: str):
    """获取习惯详情（含打卡记录）"""
    habit = await task_service.get_habit(habit_id)
    if not habit:
        return {"status": "error", "message": f"习惯 {habit_id} 不存在"}
    return {"status": "success", "habit": habit}


@router.post("/{habit_id}/checkin")
async def checkin_habit(habit_id: str, request: CheckinRequest):
    """习惯打卡"""
    return await task_service.checkin_habit(habit_id, request.count, request.note)


@router.get("/{habit_id}/stats")
async def get_habit_stats(habit_id: str):
    """获取习惯统计"""
    return await task_service.get_habit_stats(habit_id)


@router.delete("/{habit_id}")
async def delete_habit(habit_id: str):
    """删除习惯"""
    return await task_service.delete_habit(habit_id)
