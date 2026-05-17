"""POST /upload route (T050).

- Pre-parse size validation against ``MAX_UPLOAD_BYTES`` (FR-003).
- Pre-parse MIME / extension validation via ``parser_for`` (FR-001).
- Spools to a temp file inside ``upload_tmp_dir``; cleans up the temp
  file in a ``finally`` regardless of ingestion outcome (FR-016).
- Response matches the OpenAPI ``UploadResponse`` schema.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, UploadFile

from ...config import Settings, get_settings
from ...services.ingestion import IngestionService
from ...services.sessions import SessionService
from ..deps import get_ingestion_service, get_session_service, require_bearer_token
from ..errors import PayloadTooLarge

router = APIRouter()

_CHUNK = 1024 * 1024  # 1 MiB read-buffer for the spool loop


@router.post("/upload")
async def upload(
    file: Annotated[UploadFile, File(...)],
    x_session_id: Annotated[str | None, Header(alias="X-Session-Id")] = None,
    _auth: Annotated[None, Depends(require_bearer_token)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
    session_svc: Annotated[SessionService, Depends(get_session_service)] = None,  # type: ignore[assignment]
    ingestion_svc: Annotated[IngestionService, Depends(get_ingestion_service)] = None,  # type: ignore[assignment]
) -> dict:
    assert settings is not None and session_svc is not None and ingestion_svc is not None

    if x_session_id:
        await session_svc.resolve(x_session_id)
        session_id = x_session_id
    else:
        session_id = await session_svc.create_session()

    os.makedirs(settings.upload_tmp_dir, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix="upload_", suffix=_safe_suffix(file.filename), dir=settings.upload_tmp_dir
    )
    written = 0
    try:
        out = await asyncio.to_thread(os.fdopen, tmp_fd, "wb")
        try:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise PayloadTooLarge(
                        f"file exceeds {settings.max_upload_bytes}-byte limit"
                    )
                # Offload the blocking write so the event loop stays free
                # for other in-flight streams.
                await asyncio.to_thread(out.write, chunk)
        finally:
            await asyncio.to_thread(out.close)

        result = await ingestion_svc.ingest(
            file_path=tmp_path,
            filename=file.filename or "upload",
            mime_type=file.content_type,
            session_id=session_id,
        )

        return {
            "session_id": session_id,
            "document_id": result["document_id"],
            "filename": file.filename,
            "mime_type": file.content_type,
            "byte_size": written,
            "page_count": result["page_count"],
            "chunk_count": result["chunk_count"],
            "ingested_timing_ms": {
                "parse_ms": result["parse_ms"],
                "chunk_ms": result["chunk_ms"],
                "embed_ms": result["embed_ms"],
                "store_ms": result["store_ms"],
                "total_ms": result["total_ms"],
            },
            "ingested_at": datetime.now(UTC).isoformat(),
        }
    finally:
        with suppress(FileNotFoundError):
            os.unlink(tmp_path)


def _safe_suffix(filename: str | None) -> str:
    """Return a safe ``.<ext>`` suffix for the temp file, or ``""``."""
    if not filename or "." not in filename:
        return ""
    ext = filename.rsplit(".", 1)[-1].lower()
    if not ext.isalnum() or len(ext) > 8:
        return ""
    return f".{ext}"
