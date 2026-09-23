from fastapi import APIRouter
from app.v2.schemas.tasks_v2 import router as tasks_v2_router
from app.v2.schemas.quotes_v2 import router as quotes_v2_router
from app.v2.schemas.opc_v2 import router as opc_v2_router
from app.v2.schemas.automation_v2 import router as automation_v2_router
from app.api.v1 import auth, reports

router = APIRouter()
router.include_router(auth.router,      prefix="/auth",    tags=["V2-认证"])
router.include_router(tasks_v2_router,  prefix="/tasks",   tags=["V2-任务（DecisionAgent）"])
router.include_router(quotes_v2_router, prefix="/quotes",  tags=["V2-丝网报价"])
router.include_router(opc_v2_router,    prefix="/opc",     tags=["V2-OPC业务"])
router.include_router(automation_v2_router, prefix="/automation", tags=["V2-自动化"])
router.include_router(reports.router,   prefix="/reports", tags=["V2-报告"])
