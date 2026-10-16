"""
Celery 应用实例
使用 Redis 作为 broker 和 result backend
"""
from celery import Celery
from config.settings import settings

celery_app = Celery(
    "wiremesh_opc",
    broker=settings.REDIS_URL.replace("/0", "/1"),   # 用 DB1 做任务队列，DB0 留给 Memory
    backend=settings.REDIS_URL.replace("/0", "/1"),
    include=["app.tasks.task_runner", "app.tasks.lead_runner"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,           # 任务执行完才 ack，防止 worker 崩溃丢任务
    worker_prefetch_multiplier=1,  # 每个 worker 一次只取一个任务（算量任务重）
    task_soft_time_limit=1800,     # 软超时 30 分钟
    task_time_limit=2100,          # 硬超时 35 分钟（强制 kill）
    result_expires=86400,          # 结果保留 24 小时
    beat_schedule={
        "poll-public-procurement-leads": {
            "task": "wiremesh_opc.poll_leads",
            "schedule": 1800.0,
        },
    },
)
