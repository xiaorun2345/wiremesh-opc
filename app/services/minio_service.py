from minio import Minio
from minio.error import S3Error
from loguru import logger
from config.settings import settings
import os
from pathlib import Path


class MinioService:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if MinioService._initialized:
            return
        MinioService._initialized = True

        self._use_local = False
        self._local_dir = Path(settings.UPLOAD_DIR) / "minio_fallback"
        self._client = None
        self._bucket = settings.MINIO_BUCKET

        try:
            import urllib3
            http_client = urllib3.PoolManager(
                timeout=urllib3.util.Timeout(connect=2, read=10),
                maxsize=10,
            )
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
                http_client=http_client,
            )
            self._ensure_bucket()
        except Exception as e:
            logger.warning(f"MinIO 连接失败，使用本地文件降级: {e}")
            self._use_local = True
            self._local_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_bucket(self):
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info(f"MinIO bucket '{self._bucket}' 已创建")
        except S3Error as e:
            logger.warning(f"MinIO bucket 检查失败: {e}")

    def upload(self, object_name: str, data: bytes, filename: str) -> str:
        if self._use_local:
            local_path = self._local_dir / object_name.replace("/", "_")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(data)
            return object_name
        import io
        self._client.put_object(
            self._bucket, object_name, io.BytesIO(data), length=len(data),
            content_type=self._guess_content_type(filename),
        )
        return object_name

    def upload_stream(self, object_name: str, file_obj, content_length: int, filename: str) -> str:
        """流式上传：接收文件对象（如 UploadFile.file），避免全量加载到内存"""
        if self._use_local:
            local_path = self._local_dir / object_name.replace("/", "_")
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as f:
                while chunk := file_obj.read(8192):
                    f.write(chunk)
            return object_name
        self._client.put_object(
            self._bucket, object_name, file_obj, length=content_length,
            content_type=self._guess_content_type(filename),
        )
        return object_name

    def download(self, object_name: str) -> bytes:
        if self._use_local:
            local_path = self._local_dir / object_name.replace("/", "_")
            return local_path.read_bytes()
        response = self._client.get_object(self._bucket, object_name)
        return response.read()

    def delete(self, object_name: str):
        try:
            self._client.remove_object(self._bucket, object_name)
        except S3Error as e:
            logger.warning(f"MinIO 删除失败 {object_name}: {e}")

    def presigned_url(self, object_name: str, expires_seconds: int = 3600) -> str:
        """生成临时访问链接（默认 1 小时有效）"""
        from datetime import timedelta
        return self._client.presigned_get_object(
            self._bucket, object_name,
            expires=timedelta(seconds=expires_seconds),
        )

    @staticmethod
    def _guess_content_type(filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower()
        return {
            "pdf": "application/pdf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "dwg": "application/octet-stream",
            "dxf": "application/octet-stream",
        }.get(ext, "application/octet-stream")
