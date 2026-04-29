"""
笔记管理路由
POST   /api/notes — 创建笔记
GET    /api/notes — 笔记列表
GET    /api/notes/{note_id} — 获取笔记
PUT    /api/notes/{note_id} — 更新笔记
DELETE /api/notes/{note_id} — 删除笔记
"""
from fastapi import APIRouter, Query

from models.schemas import BaseModel, Field
from services import note_service

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteCreateRequest(BaseModel):
    title: str = Field(..., description="笔记标题")
    content: str = Field("", description="笔记内容 (Markdown)")
    content_type: str = Field("markdown", description="内容类型: markdown/plain/text")
    tags: list[str] = Field([], description="标签列表")
    task_id: str = Field(None, description="关联任务ID")


class NoteUpdateRequest(BaseModel):
    title: str = Field(None, description="笔记标题")
    content: str = Field(None, description="笔记内容")
    tags: list[str] = Field(None, description="标签列表")


@router.post("/")
async def create_note(request: NoteCreateRequest):
    """创建笔记"""
    result = await note_service.create_note(
        title=request.title,
        content=request.content,
        content_type=request.content_type,
        tags=request.tags,
        task_id=request.task_id,
    )
    return result


@router.get("/")
async def list_notes(
    keyword: str = Query("", description="搜索关键词"),
    tag: str = Query("", description="标签筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取笔记列表"""
    result = await note_service.get_all_notes(
        keyword=keyword,
        tag=tag,
        page=page,
        page_size=page_size,
    )
    return result


@router.get("/{note_id}")
async def get_note(note_id: str):
    """获取单个笔记"""
    note = await note_service.get_note(note_id)
    if not note:
        return {"status": "error", "message": f"笔记 {note_id} 不存在"}
    return {"status": "success", "note": note}


@router.put("/{note_id}")
async def update_note(note_id: str, request: NoteUpdateRequest):
    """更新笔记"""
    result = await note_service.update_note(
        note_id=note_id,
        title=request.title,
        content=request.content,
        tags=request.tags,
    )
    return result


@router.delete("/{note_id}")
async def delete_note(note_id: str):
    """删除笔记"""
    return await note_service.delete_note(note_id)
