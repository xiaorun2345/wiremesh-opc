from __future__ import annotations

import json
import urllib.parse
import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.utils.db import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.task import Task
from app.schemas.schemas import TaskResponse, StepStatus, ResumeRequest, ResumeResponse
from app.v2.core.task_service_v2 import TaskServiceV2 as TaskService

router = APIRouter()

ALLOWED_TYPES = {"pdf", "dwg", "dxf", "jpg", "jpeg", "png"}
MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100MB

# 文件头魔数校验
MAGIC_BYTES = {
    b"\x25\x50\x44\x46": "pdf",          # %PDF
    b"\xAC\x1C\x00\x00": "dwg",          # DWG
    b"\x41\x43\x31\x30": "dxf",          # AC10 (DXF)
    b"\xFF\xD8\xFF":      "jpg",          # JPEG
    b"\x89\x50\x4E\x47": "png",          # PNG
}


def detect_file_type(header: bytes) -> str | None:
    for magic, ftype in MAGIC_BYTES.items():
        if header.startswith(magic):
            return ftype
    return None


@router.post("/upload", response_model=TaskResponse, status_code=201)
async def upload_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 读取文件头校验（只读 16 字节，不加载全文件）
    header = await file.read(16)
    await file.seek(0)

    detected = detect_file_type(header)
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if ext not in ALLOWED_TYPES:
        raise HTTPException(400, {"error": "UNSUPPORTED_FILE_TYPE", "message": f"不支持的文件格式，支持：{'/'.join(ALLOWED_TYPES)}"})
    if detected is None:
        raise HTTPException(400, {"error": "FILE_CORRUPTED", "message": "文件损坏或格式不符"})

    # 获取文件大小（底层 SpooledTemporaryFile 支持 whence 参数）
    file.file.seek(0, 2)  # seek to end
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size == 0:
        raise HTTPException(400, {"error": "FILE_CORRUPTED", "message": "文件为空"})
    if file_size > MAX_SIZE_BYTES:
        raise HTTPException(400, {"error": "FILE_TOO_LARGE", "message": "文件超过 100MB 限制"})

    task_id = str(uuid.uuid4())
    svc = TaskService(db)
    # 流式上传：直接传 file.file 对象，不读全文件到内存
    task = await svc.create_task_streaming(task_id, current_user.id, file.filename, detected, file.file, file_size)

    # 后台任务处理（FastAPI 会在响应返回后执行）
    background_tasks.add_task(_run_task_background_v1, task_id)

    return _task_to_response(task)


async def _run_task_background_v1(task_id: str):
    """在后台运行任务，使用 V2 TaskService"""
    from app.utils.db import get_db
    from app.v2.core.task_service_v2 import TaskServiceV2

    async for db in get_db():
        svc = TaskServiceV2(db)
        await svc.run_task(task_id)
        break


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_owned_task(task_id, current_user.id, db)

    # PAUSED 状态时，从 Redis 读取中间数据暴露给用户
    intermediate_data = None
    if task.status == "PAUSED":
        from app.core.memory.redis_memory import TaskMemory
        mem = TaskMemory(task_id)
        intermediate_data = await mem.get("human_review_data")

    return _task_to_response(task, intermediate_data=intermediate_data)


@router.post("/{task_id}/resume", response_model=ResumeResponse)
async def resume_task(
    task_id: str,
    body: ResumeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_owned_task(task_id, current_user.id, db)
    if task.status == "RUNNING":
        raise HTTPException(409, {"error": "TASK_ALREADY_RUNNING", "message": "任务正在运行中"})
    if task.status not in ("FAILED", "PAUSED"):
        raise HTTPException(400, {"error": "INVALID_STATUS", "message": f"当前状态 {task.status} 不可续跑"})

    svc = TaskService(db)
    resumed_step = await svc.resume_task(task_id, body.override_data)
    background_tasks.add_task(svc.run_task, task_id, resumed_step)

    return ResumeResponse(task_id=task_id, status="RUNNING", resumed_from_step=resumed_step)


@router.delete("/{task_id}", status_code=204)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_owned_task(task_id, current_user.id, db)
    svc = TaskService(db)
    await svc.cancel_task(task.id)


# ── 内部工具 ──────────────────────────────────────────────────
@router.get("/stats")
async def get_task_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户任务各状态数量统计，用于 Dashboard 概览"""
    from sqlalchemy import func
    result = await db.execute(
        select(Task.status, func.count(Task.id).label("count"))
        .where(Task.user_id == current_user.id)
        .group_by(Task.status)
    )
    rows = result.all()
    # 初始化所有状态为 0
    stats = {s: 0 for s in ("PENDING", "RUNNING", "SUCCESS", "FAILED", "PAUSED", "CANCELLED")}
    for row in rows:
        stats[row.status] = row.count
    stats["total"] = sum(stats.values())
    return stats


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: str | None = Query(None, description="按状态过滤：PENDING/RUNNING/SUCCESS/FAILED/PAUSED/CANCELLED"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前用户的任务列表"""
    stmt = select(Task).where(Task.user_id == current_user.id)
    if status:
        stmt = stmt.where(Task.status == status.upper())
    stmt = stmt.order_by(desc(Task.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [_task_to_response(t) for t in tasks]


@router.get("/{task_id}/file")
async def download_original_file(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载任务的原始上传文件（图纸/PDF/图片）"""
    task = await _get_owned_task(task_id, current_user.id, db)

    from app.services.minio_service import MinioService
    try:
        data = MinioService().download(task.file_id)
    except Exception as e:
        raise HTTPException(404, {"error": "FILE_NOT_FOUND", "message": f"原始文件不存在: {e}"})

    # 根据文件类型设置 Content-Type
    content_type_map = {
        "pdf":  "application/pdf",
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "png":  "image/png",
        "dwg":  "application/octet-stream",
        "dxf":  "application/octet-stream",
    }
    content_type = content_type_map.get(task.file_type, "application/octet-stream")

    # URL-encode filename for RFC 5987 Content-Disposition header
    encoded_name = urllib.parse.quote(task.file_name, safe="")

    return StreamingResponse(
        io.BytesIO(data),
        media_type=content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
            "Content-Length": str(len(data)),
        },
    )


async def _get_owned_task(task_id: str, user_id: str, db: AsyncSession) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, {"error": "TASK_NOT_FOUND", "message": "任务不存在"})
    if task.user_id != user_id:
        raise HTTPException(403, {"error": "FORBIDDEN", "message": "无权操作此任务"})
    return task


def _task_to_response(task: Task, intermediate_data: dict | None = None) -> TaskResponse:
    steps = []
    if task.steps_json:
        try:
            steps = [StepStatus(**s) for s in json.loads(task.steps_json)]
        except Exception:
            pass
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        current_step=task.current_step,
        progress=task.progress,
        steps=steps,
        file_name=task.file_name,
        file_type=task.file_type,
        file_size=getattr(task, 'file_size', 0),
        created_at=task.created_at,
        updated_at=task.updated_at,
        intermediate_data=intermediate_data,
        error_msg=task.error_msg,
    )
