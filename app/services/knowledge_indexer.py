"""Chunk and index OPC knowledge documents in ChromaDB."""
from config.settings import settings


def chunk_text(text: str, size: int = 600, overlap: int = 80) -> list[str]:
    clean = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + size)
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(start + 1, end - overlap)
    return chunks


def index_document(owner_id: str, document_id: str, name: str, category: str, content: str) -> int:
    import chromadb

    chunks = chunk_text(content)
    client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    collection = client.get_or_create_collection(f"opc_{owner_id.replace('-', '_')}")
    old = collection.get(where={"document_id": document_id})
    if old.get("ids"):
        collection.delete(ids=old["ids"])
    if chunks:
        collection.add(
            ids=[f"{document_id}:{index}" for index in range(len(chunks))],
            documents=chunks,
            metadatas=[{"document_id":document_id,"name":name,"category":category,"chunk_index":index} for index in range(len(chunks))],
        )
    return len(chunks)


def search_knowledge(owner_id: str, query: str, limit: int = 5) -> list[dict]:
    import chromadb

    client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    collection = client.get_or_create_collection(f"opc_{owner_id.replace('-', '_')}")
    result = collection.query(query_texts=[query], n_results=limit, include=["documents","metadatas","distances"])
    docs=result.get("documents",[[]])[0];meta=result.get("metadatas",[[]])[0];dist=result.get("distances",[[]])[0]
    return [{"content":doc,"metadata":m,"distance":d} for doc,m,d in zip(docs,meta,dist)]
