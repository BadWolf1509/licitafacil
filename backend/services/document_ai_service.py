"""
Document AI service for table extraction.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from config import PAID_SERVICES_ENABLED

load_dotenv()

try:
    from google.cloud import documentai  # type: ignore
    _DOC_AI_AVAILABLE = True
except Exception:
    documentai = None  # type: ignore[assignment]
    _DOC_AI_AVAILABLE = False


class DocumentAIService:
    """Wrapper around Google Document AI to extract tables."""

    def __init__(self) -> None:
        self._client: Optional[Any] = None

    @property
    def is_available(self) -> bool:
        return _DOC_AI_AVAILABLE

    @property
    def is_configured(self) -> bool:
        if not _DOC_AI_AVAILABLE:
            return False
        if not PAID_SERVICES_ENABLED:
            return False
        return bool(
            os.getenv("DOCUMENT_AI_PROJECT_ID")
            and os.getenv("DOCUMENT_AI_LOCATION")
            and os.getenv("DOCUMENT_AI_PROCESSOR_ID")
        )

    def _get_client(self):
        if self._client is None:
            if not _DOC_AI_AVAILABLE:
                raise Exception("google-cloud-documentai is not installed")
            location = os.getenv("DOCUMENT_AI_LOCATION", "us").lower()
            client_options = None
            if location and location != "us":
                client_options = {"api_endpoint": f"{location}-documentai.googleapis.com"}
            self._client = documentai.DocumentProcessorServiceClient(client_options=client_options)
        return self._client

    def _get_processor_name(self) -> str:
        project_id = os.getenv("DOCUMENT_AI_PROJECT_ID", "")
        location = os.getenv("DOCUMENT_AI_LOCATION", "us")
        processor_id = os.getenv("DOCUMENT_AI_PROCESSOR_ID", "")
        version_id = os.getenv("DOCUMENT_AI_PROCESSOR_VERSION")
        client = self._get_client()
        if version_id:
            return client.processor_version_path(project_id, location, processor_id, version_id)
        return client.processor_path(project_id, location, processor_id)

    def _guess_mime_type(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return "application/pdf"
        if ext in {".png"}:
            return "image/png"
        if ext in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if ext in {".tif", ".tiff"}:
            return "image/tiff"
        return "application/octet-stream"

    def _text_from_layout(self, document: Any, layout: Any) -> str:
        if not layout or not getattr(layout, "text_anchor", None):
            return ""
        text = ""
        for segment in layout.text_anchor.text_segments:
            start = int(segment.start_index) if segment.start_index is not None else 0
            end = int(segment.end_index) if segment.end_index is not None else 0
            if end > start:
                text += document.text[start:end]
        return " ".join(text.split()).strip()

    def _extract_tables_from_document(self, document: Any) -> List[Dict[str, Any]]:
        tables: List[Dict[str, Any]] = []
        pages = getattr(document, "pages", None) or []
        for page_index, page in enumerate(pages):
            page_tables = getattr(page, "tables", None) or []
            for table in page_tables:
                rows = []
                header_rows = getattr(table, "header_rows", None) or []
                body_rows = getattr(table, "body_rows", None) or []
                for row in list(header_rows) + list(body_rows):
                    cells = []
                    for cell in getattr(row, "cells", None) or []:
                        cells.append(self._text_from_layout(document, cell.layout))
                    if any(cells):
                        rows.append(cells)
                if rows:
                    tables.append({"page": page_index + 1, "rows": rows})
        return tables

    def extract_tables(self, file_path: str, use_native_pdf_parsing: bool = False) -> Dict[str, Any]:
        if not self.is_configured:
            return {"tables": [], "pages": 0, "error": "not_configured"}
        client = self._get_client()
        name = self._get_processor_name()
        mime_type = self._guess_mime_type(file_path)
        with open(file_path, "rb") as handle:
            content = handle.read()
        raw_document = documentai.RawDocument(content=content, mime_type=mime_type)
        process_options = None
        if use_native_pdf_parsing and mime_type == "application/pdf":
            process_options = documentai.ProcessOptions(
                ocr_config=documentai.OcrConfig(enable_native_pdf_parsing=True)
            )
        if process_options:
            request = documentai.ProcessRequest(
                name=name,
                raw_document=raw_document,
                process_options=process_options
            )
        else:
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document
        tables = self._extract_tables_from_document(document)
        pages = len(getattr(document, "pages", None) or [])
        return {"tables": tables, "pages": pages}


document_ai_service = DocumentAIService()
