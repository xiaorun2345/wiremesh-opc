"""
国标文档导入脚本
将 data/standards/ 目录下的 PDF/TXT 文件切片后导入 ChromaDB

用法：
    python scripts/init_standards.py
    python scripts/init_standards.py --dir data/standards --chunk-size 500
"""
import sys
import os
import argparse
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from loguru import logger


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """按字符数切片，带重叠"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


def load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_pdf(path: Path) -> str:
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text
    except Exception as e:
        logger.warning(f"PDF 读取失败 {path}: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser(description="导入国标文档到 ChromaDB")
    parser.add_argument("--dir",        default="data/standards", help="文档目录")
    parser.add_argument("--chunk-size", type=int, default=500,    help="切片字符数")
    parser.add_argument("--reset",      action="store_true",       help="清空后重新导入")
    args = parser.parse_args()

    standards_dir = Path(args.dir)
    if not standards_dir.exists():
        logger.error(f"目录不存在: {standards_dir}")
        sys.exit(1)

    import chromadb
    client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)

    if args.reset:
        try:
            client.delete_collection("standards")
            logger.info("已清空 standards 集合")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name="standards",
        metadata={"hnsw:space": "cosine"},
    )

    files = list(standards_dir.glob("**/*.txt")) + list(standards_dir.glob("**/*.pdf"))
    if not files:
        logger.warning(f"未找到文档文件（.txt/.pdf）in {standards_dir}")
        return

    total_chunks = 0
    for file_path in files:
        logger.info(f"处理: {file_path.name}")
        text = load_pdf(file_path) if file_path.suffix == ".pdf" else load_txt(file_path)
        if not text.strip():
            logger.warning(f"  空文件，跳过")
            continue

        chunks = chunk_text(text, chunk_size=args.chunk_size)
        ids       = [f"{file_path.stem}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": file_path.name, "chunk": i} for i in range(len(chunks))]

        # 批量写入（每批 100 条）
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            collection.add(
                documents=ids[i:i+batch_size],
                ids=ids[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
            )
            # 用文本作为 document，ChromaDB 会自动 embedding
            collection.upsert(
                documents=chunks[i:i+batch_size],
                ids=ids[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
            )

        logger.info(f"  导入 {len(chunks)} 个切片")
        total_chunks += len(chunks)

    logger.info(f"导入完成，共 {len(files)} 个文件，{total_chunks} 个切片")


if __name__ == "__main__":
    main()
