"""
装修国标标准管理 API
===================
- 上传 PDF 标准文档
- 提取条文并导入 ChromaDB
- 查询已导入的标准列表
"""

import os
import json
import shutil
import asyncio
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from loguru import logger

from app.utils.auth import get_current_user
from app.utils.db import get_db
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

# 标准文档存储目录
STANDARDS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "standards"
STANDARDS_DIR.mkdir(parents=True, exist_ok=True)


# ========== Schemas ==========

class StandardInfo(BaseModel):
    filename: str
    standard_name: str
    page_count: int
    section_count: int
    categories: list[str]
    status: str  # "pending", "extracting", "imported", "failed"
    created_at: str


class ImportResponse(BaseModel):
    message: str
    standard_name: str
    section_count: int = 0


class StandardsListResponse(BaseModel):
    total: int
    standards: list[StandardInfo]


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


class QueryResult(BaseModel):
    standard_name: str
    section: str
    chapter: str
    content: str
    keywords: list[str]
    is_mandatory: bool
    score: float


class QueryResponse(BaseModel):
    query: str
    results: list[QueryResult]


# ========== Helper ==========

def get_import_status_file(filename: str) -> Path:
    return STANDARDS_DIR / f"{filename}.status"


def save_import_status(filename: str, status: dict):
    status_file = get_import_status_file(filename)
    with open(status_file, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def load_import_status(filename: str) -> dict:
    status_file = get_import_status_file(filename)
    if status_file.exists():
        with open(status_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


# ========== Background Import Task ==========

async def import_pdf_background(pdf_path: str, filename: str):
    """后台任务：提取 PDF 条文并导入 ChromaDB"""
    import sys
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))

    from tools.extract_standards_to_rag import (
        parse_pdf_smart,
        chunk_by_sections,
        extract_standard_name,
        categorize_standard,
        extract_keywords,
        get_bge_embedding,
        MANDATORY_PATTERN,
    )
    import chromadb

    save_import_status(filename, {
        "filename": filename,
        "status": "extracting",
        "standard_name": "",
        "section_count": 0,
    })

    try:
        # 1. 解析 PDF
        standard_name = extract_standard_name(filename)
        text = parse_pdf_smart(str(pdf_path))

        if not text:
            save_import_status(filename, {
                "filename": filename,
                "status": "failed",
                "standard_name": standard_name,
                "error": "PDF 解析失败，可能是扫描版或图片为主",
            })
            return

        # 2. 分块
        chunks = chunk_by_sections(text, standard_name)
        category = categorize_standard(standard_name)

        standards = []
        for chunk in chunks:
            standards.append({
                "id": chunk["id"],
                "standard_name": standard_name,
                "section": chunk["section"],
                "chapter": chunk.get("chapter", ""),
                "content": chunk["content"],
                "keywords": extract_keywords(chunk["content"]),
                "category": category,
                "is_mandatory": bool(MANDATORY_PATTERN.search(chunk["content"])),
                "source": "pdf_upload",
            })

        # 去重
        seen = set()
        unique = []
        for s in standards:
            if s["id"] not in seen:
                seen.add(s["id"])
                unique.append(s)

        if not unique:
            save_import_status(filename, {
                "filename": filename,
                "status": "failed",
                "standard_name": standard_name,
                "error": "未提取到任何条文",
            })
            return

        # 3. 导入 ChromaDB
        client = chromadb.PersistentClient(path=str(Path.home() / ".chromadb"))
        collection = client.get_or_create_collection(
            name="standards",
            metadata={"hnsw:space": "cosine"}
        )

        # 检查已存在
        existing_ids = set()
        if collection.count() > 0:
            existing = collection.get(include=[])
            existing_ids = set(existing.get("ids", []))

        new_standards = [s for s in unique if s["id"] not in existing_ids]
        if not new_standards:
            save_import_status(filename, {
                "filename": filename,
                "status": "imported",
                "standard_name": standard_name,
                "section_count": len(unique),
                "message": "条文已存在，未重复导入",
            })
            return

        # 批量导入（让 ChromaDB 自动用默认模型生成向量，避免维度不一致）
        batch_size = 100
        for i in range(0, len(new_standards), batch_size):
            batch = new_standards[i:i+batch_size]
            collection.add(
                ids=[s["id"] for s in batch],
                documents=[s["content"] for s in batch],
                metadatas=[{
                    "standard_name": s["standard_name"],
                    "section": s["section"],
                    "chapter": s.get("chapter", ""),
                    "category": s["category"],
                    "keywords": json.dumps(s.get("keywords", [])),
                    "is_mandatory": s.get("is_mandatory", False),
                    "source": s.get("source", "pdf_upload"),
                } for s in batch]
            )

        # 4. 保存状态
        categories = list(set(s["category"] for s in unique))
        save_import_status(filename, {
            "filename": filename,
            "status": "imported",
            "standard_name": standard_name,
            "section_count": len(unique),
            "categories": categories,
            "message": f"成功导入 {len(new_standards)} 条条文",
        })

        logger.info(f"[Standards] {filename}: 导入 {len(new_standards)} 条条文完成")

    except Exception as e:
        logger.error(f"[Standards] {filename}: 导入失败 {e}")
        save_import_status(filename, {
            "filename": filename,
            "status": "failed",
            "standard_name": standard_name if 'standard_name' in locals() else "",
            "error": str(e),
        })


# ========== API Routes ==========

@router.post("/upload", response_model=ImportResponse)
async def upload_standard(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
):
    """上传 PDF 标准文档，后台提取并导入 ChromaDB"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, {"error": "INVALID_FORMAT", "message": "只支持 PDF 文件"})

    # 保存文件
    filename = file.filename
    pdf_path = STANDARDS_DIR / filename

    # 如果已存在，返回提示
    if pdf_path.exists():
        return ImportResponse(
            message=f"文件 {filename} 已存在",
            standard_name=filename,
        )

    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 启动后台导入
    if background_tasks:
        background_tasks.add_task(import_pdf_background, str(pdf_path), filename)

    return ImportResponse(
        message=f"文件 {filename} 已上传，正在后台提取条文",
        standard_name=filename,
    )


@router.get("/list", response_model=StandardsListResponse)
async def list_standards(
    current_user: User = Depends(get_current_user),
):
    """查询已导入的标准文档列表"""
    import glob

    # 扫描所有 PDF 文件
    pdf_files = list(STANDARDS_DIR.glob("*.pdf"))
    standards = []

    for pdf_path in pdf_files:
        filename = pdf_path.name
        status = load_import_status(filename)

        standard_info = StandardInfo(
            filename=filename,
            standard_name=status.get("standard_name", ""),
            page_count=0,  # 可选，需要解析 PDF 才能获取
            section_count=status.get("section_count", 0),
            categories=status.get("categories", []),
            status=status.get("status", "pending"),
            created_at=status.get("created_at", pdf_path.stat().st_mtime.__str__()),
        )
        standards.append(standard_info)

    return StandardsListResponse(
        total=len(standards),
        standards=sorted(standards, key=lambda x: x.standard_name),
    )


@router.post("/query", response_model=QueryResponse)
async def query_standards(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
):
    """RAG 检索：向量 + 关键词混合查询"""
    import chromadb
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

    client = chromadb.PersistentClient(path=str(Path.home() / ".chromadb"))
    collection = client.get_collection("standards")

    # 向量检索
    results = collection.query(
        query_texts=[request.query],
        n_results=request.top_k,
        include=["documents", "metadatas", "distances"]
    )

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    query_results = []
    for doc, meta, dist in zip(docs, metas, distances):
        query_results.append(QueryResult(
            standard_name=meta.get("standard_name", ""),
            section=meta.get("section", ""),
            chapter=meta.get("chapter", ""),
            content=doc[:500],  # 截断过长内容
            keywords=json.loads(meta.get("keywords", "[]")),
            is_mandatory=meta.get("is_mandatory", False),
            score=round(1 - dist, 4),  # 距离转相似度
        ))

    return QueryResponse(
        query=request.query,
        results=query_results,
    )


@router.delete("/{filename}")
async def delete_standard(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """删除已导入的标准文档（仅删除文件，ChromaDB 条文需要手动清理）"""
    pdf_path = STANDARDS_DIR / filename
    status_file = get_import_status_file(filename)

    if not pdf_path.exists():
        raise HTTPException(404, {"error": "NOT_FOUND", "message": "文件不存在"})

    pdf_path.unlink()
    if status_file.exists():
        status_file.unlink()

    return {"message": f"已删除 {filename}"}


@router.get("/status/{filename}")
async def get_import_status(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """查询导入任务状态"""
    status = load_import_status(filename)
    if not status:
        raise HTTPException(404, {"error": "NOT_FOUND", "message": "未找到导入状态"})
    return status
