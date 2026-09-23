from fastapi import APIRouter
from app.api.v1 import tasks, reports, auth, standards

router = APIRouter()
router.include_router(auth.router,       prefix="/auth",      tags=["认证"])
router.include_router(tasks.router,      prefix="/tasks",     tags=["任务"])
router.include_router(reports.router,    prefix="/reports",   tags=["报告"])
router.include_router(standards.router,  prefix="/standards", tags=["标准管理"])
