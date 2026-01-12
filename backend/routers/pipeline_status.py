"""
Endpoints para status e controle do pipeline de extração em cascata.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from typing import Dict, Any, Optional
import tempfile
import os

from auth import get_current_user
from models import Usuario
from services.cascade_pipeline import cascade_pipeline, ExtractionPipeline
from services.quality_detector import quality_detector
from services.azure_document_service import azure_document_service
from services.ai_analyzer import ai_analyzer
from services.ocr_service import ocr_service

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.get("/status")
async def get_pipeline_status(
    current_user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retorna status do pipeline e serviços disponíveis.
    """
    return {
        "pipeline": cascade_pipeline.get_status(),
        "services": {
            "pdfplumber": {
                "available": True,
                "cost_per_page": 0.0
            },
            "easyocr": {
                "available": ocr_service.is_available if hasattr(ocr_service, 'is_available') else True,
                "cost_per_page": 0.0
            },
            "azure_document_intelligence": {
                "available": azure_document_service.is_configured,
                "cost_per_page": 0.001,
                "free_tier": "500 páginas/mês"
            },
            "openai_gpt4o_vision": {
                "available": ai_analyzer.is_configured,
                "cost_per_page": 0.10
            }
        },
        "cost_estimate": {
            "facil": "~R$ 0.002/página (pdfplumber + GPT-4o-mini)",
            "medio": "~R$ 0.002/página (EasyOCR + GPT-4o-mini)",
            "dificil": "~R$ 0.011/página (Azure Read + GPT-4o-mini)",
            "muito_dificil": "~R$ 0.10/página (GPT-4o Vision)"
        }
    }


@router.post("/analyze-quality")
async def analyze_document_quality(
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Analisa a qualidade de um documento e retorna recomendação de pipeline.
    Não processa o documento, apenas avalia a qualidade.
    """
    # Salvar arquivo temporário
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".pdf"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Analisar qualidade
        report = quality_detector.analyze_document(tmp_path)

        return {
            "filename": file.filename,
            "quality": report.quality.value,
            "quality_description": {
                "native": "PDF nativo com texto selecionável",
                "easy": "Escaneado com boa qualidade",
                "medium": "Escaneado com qualidade média",
                "hard": "Escaneado com baixa qualidade",
                "very_hard": "Documento muito degradado"
            }.get(report.quality.value, "Desconhecido"),
            "recommended_pipeline": report.recommended_pipeline.value,
            "pipeline_description": {
                "native_text": "Extração nativa (pdfplumber)",
                "local_ocr": "OCR local (EasyOCR)",
                "cloud_ocr": "OCR na nuvem (Azure)",
                "vision_ai": "Análise visual (GPT-4o Vision)"
            }.get(report.recommended_pipeline.value, "Desconhecido"),
            "confidence": report.confidence,
            "estimated_cost_brl": report.estimated_cost,
            "summary": report.summary,
            "pages_analysis": report.pages_analysis[:5]  # Limitar a 5 páginas no preview
        }
    finally:
        # Limpar arquivo temporário
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/process")
async def process_with_cascade(
    file: UploadFile = File(...),
    force_pipeline: Optional[str] = None,
    current_user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Processa um documento usando o pipeline em cascata.

    Args:
        file: Arquivo PDF ou imagem
        force_pipeline: Forçar um pipeline específico (native_text, local_ocr, cloud_ocr, vision_ai)
    """
    # Validar pipeline forçado
    pipeline_override = None
    if force_pipeline:
        try:
            pipeline_override = ExtractionPipeline(force_pipeline)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pipeline inválido: {force_pipeline}. "
                       f"Use: native_text, local_ocr, cloud_ocr, vision_ai"
            )

    # Salvar arquivo temporário
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".pdf"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Configurar pipeline
        if pipeline_override:
            cascade_pipeline.configure(force_pipeline=pipeline_override)

        # Processar documento
        result = cascade_pipeline.process(tmp_path)

        # Resetar configuração
        cascade_pipeline.configure(force_pipeline=None)

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro no processamento: {', '.join(result.errors)}"
            )

        return {
            "success": result.success,
            "filename": file.filename,
            "pipeline_used": result.pipeline_used.value,
            "stages_executed": result.stages_executed,
            "processing_time_seconds": round(result.processing_time, 2),
            "cost_estimate_brl": result.cost_estimate,
            "quality": {
                "level": result.quality_report.quality.value if result.quality_report else None,
                "confidence": result.quality_report.confidence if result.quality_report else None
            },
            "data": result.data,
            "text_preview": result.text[:1000] if result.text else None,
            "debug_info": result.debug_info
        }
    finally:
        # Limpar arquivo temporário
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/cost-estimate")
async def estimate_processing_cost(
    num_pages: int = 1,
    quality: str = "medium",
    current_user: Usuario = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Estima o custo de processamento baseado no número de páginas e qualidade.
    """
    # Mapear qualidade para pipeline
    quality_pipeline_map = {
        "native": ExtractionPipeline.NATIVE_TEXT,
        "easy": ExtractionPipeline.LOCAL_OCR,
        "medium": ExtractionPipeline.LOCAL_OCR,
        "hard": ExtractionPipeline.CLOUD_OCR,
        "very_hard": ExtractionPipeline.VISION_AI
    }

    pipeline = quality_pipeline_map.get(quality.lower(), ExtractionPipeline.LOCAL_OCR)
    estimate = quality_detector.get_cost_estimate(pipeline, num_pages)

    return {
        "num_pages": num_pages,
        "quality": quality,
        "pipeline": estimate["pipeline"],
        "cost_per_page_brl": estimate["cost_per_page"],
        "total_cost_brl": estimate["total_cost_brl"],
        "total_cost_usd": estimate["total_cost_usd"]
    }
