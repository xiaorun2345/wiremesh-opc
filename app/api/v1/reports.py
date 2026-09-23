from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import io

from app.utils.db import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.models.task import Task
from app.models.report import Report
from app.schemas.schemas import ReportMeta
from app.services.minio_service import MinioService

router = APIRouter()


@router.get("/{task_id}", response_model=ReportMeta)
async def get_report_meta(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_task(task_id, current_user.id, db)
    result = await db.execute(select(Report).where(Report.task_id == task_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, {"error": "REPORT_NOT_FOUND", "message": "报告不存在或任务未完成"})
    return ReportMeta(
        task_id=task_id,
        pdf_available=bool(report.pdf_path),
        excel_available=bool(report.excel_path),
        created_at=report.created_at,
    )


@router.get("/{task_id}/download")
async def download_report(
    task_id: str,
    format: str = "pdf",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_task(task_id, current_user.id, db)
    result = await db.execute(select(Report).where(Report.task_id == task_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(404, {"error": "REPORT_NOT_FOUND", "message": "报告不存在"})

    if format == "pdf":
        if not report.pdf_path:
            raise HTTPException(404, {"error": "REPORT_NOT_FOUND", "message": "PDF 报告不存在"})
        data = MinioService().download(report.pdf_path)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report_{task_id}.pdf"'},
        )
    elif format == "excel":
        if not report.excel_path:
            raise HTTPException(404, {"error": "REPORT_NOT_FOUND", "message": "Excel 报告不存在"})
        data = MinioService().download(report.excel_path)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="report_{task_id}.xlsx"'},
        )
    else:
        raise HTTPException(400, {"error": "INVALID_FORMAT", "message": "format 只支持 pdf 或 excel"})


async def _get_owned_task(task_id: str, user_id: str, db: AsyncSession) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, {"error": "TASK_NOT_FOUND", "message": "任务不存在"})
    if task.user_id != user_id:
        raise HTTPException(403, {"error": "FORBIDDEN", "message": "无权操作此任务"})
    return task
