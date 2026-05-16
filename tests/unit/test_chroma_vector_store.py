import pytest
import tempfile

HAS_CHROMADB = False
try:
    import chromadb  # type: ignore

    HAS_CHROMADB = True
except Exception:
    HAS_CHROMADB = False

from src.vector_store.chroma import ChromaVectorStore
from src.models.chunk import Chunk


@pytest.mark.skipif(not HAS_CHROMADB, reason="chromadb not installed")
@pytest.mark.asyncio
async def test_chroma_vector_store_basic(tmp_path):
    store = ChromaVectorStore(persist_directory=str(tmp_path))
    session_id = "session-1"
    chunk = Chunk(
        chunk_id="doc1:0",
        document_id="doc1",
        session_id=session_id,
        sequence_index=0,
        text="hello world",
        page_number=1,
        section_path=None,
        char_start=0,
        char_end=11,
    )
    emb = [[0.1] * 8]
    await store.add(session_id, [chunk], emb)
    results = await store.search(session_id, emb[0], k=1)
    assert len(results) >= 1
    c, score = results[0]
    assert c.chunk_id == chunk.chunk_id
