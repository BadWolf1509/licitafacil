# Pipeline de Extração em Cascata - Guia de Configuração

## Visão Geral

O pipeline em cascata otimiza o custo-benefício da extração de documentos, usando a ferramenta mais barata que funcione para cada tipo de documento.

```
Documento → Análise de Qualidade → Pipeline Apropriado → Resultado
                    ↓
    ┌───────────────┼───────────────┬───────────────┐
    ↓               ↓               ↓               ↓
 NATIVE_TEXT    LOCAL_OCR      CLOUD_OCR      VISION_AI
 (pdfplumber)   (EasyOCR)      (Azure)        (GPT-4o)
  R$ 0.002      R$ 0.002       R$ 0.011       R$ 0.10
```

## Instalação de Dependências

Adicione ao `requirements.txt`:

```
# Azure Document Intelligence (OCR Cloud)
azure-ai-documentintelligence==1.0.0
azure-core==1.30.0

# Processamento de imagem (pré-processamento para OCR)
scipy==1.11.4
```

Instale com:
```bash
pip install azure-ai-documentintelligence azure-core scipy
```

## Variáveis de Ambiente

Adicione ao `.env`:

```env
# =======================
# Azure Document Intelligence (OCR Cloud - fallback para documentos difíceis)
# =======================
# Para obter credenciais: https://portal.azure.com -> Document Intelligence
# Free tier: 500 páginas/mês grátis
AZURE_DOCUMENT_ENDPOINT=https://seu-recurso.cognitiveservices.azure.com/
AZURE_DOCUMENT_KEY=sua-chave-aqui

# =======================
# Pipeline em Cascata (Configurações)
# =======================
# Habilitar pré-processamento de imagem (deskew, contraste, ruído)
PIPELINE_ENABLE_PREPROCESSING=true

# Habilitar Azure como fallback para OCR local
PIPELINE_ENABLE_AZURE=true

# Habilitar GPT-4o Vision como último recurso
PIPELINE_ENABLE_VISION=true

# Confiança mínima para aceitar resultado do OCR local (0-1)
PIPELINE_MIN_CONFIDENCE_LOCAL=0.70

# Confiança mínima para aceitar resultado do Azure (0-1)
PIPELINE_MIN_CONFIDENCE_CLOUD=0.85
```

## Configuração do Azure Document Intelligence

### 1. Criar recurso no Azure Portal

1. Acesse [portal.azure.com](https://portal.azure.com)
2. Clique em "Criar recurso"
3. Busque por "Document Intelligence"
4. Selecione o tier **F0 (Free)** para 500 páginas/mês grátis
5. Após criar, vá em "Chaves e Ponto de Extremidade"
6. Copie:
   - **Endpoint**: `https://seu-recurso.cognitiveservices.azure.com/`
   - **Chave**: uma das duas chaves disponíveis

### 2. Adicionar credenciais ao .env

```env
AZURE_DOCUMENT_ENDPOINT=https://seu-recurso.cognitiveservices.azure.com/
AZURE_DOCUMENT_KEY=sua-chave-aqui
```

## Registrar Rotas no FastAPI

Adicione ao `main.py`:

```python
from routers.pipeline_status import router as pipeline_router

app.include_router(pipeline_router)
```

## Endpoints Disponíveis

### GET /pipeline/status
Retorna status do pipeline e serviços disponíveis.

```json
{
  "services": {
    "pdfplumber": {"available": true, "cost_per_page": 0.0},
    "easyocr": {"available": true, "cost_per_page": 0.0},
    "azure_document_intelligence": {"available": true, "cost_per_page": 0.001},
    "openai_gpt4o_vision": {"available": true, "cost_per_page": 0.10}
  }
}
```

### POST /pipeline/analyze-quality
Analisa qualidade de um documento sem processá-lo.

**Request:** Form-data com arquivo PDF ou imagem

**Response:**
```json
{
  "quality": "medium",
  "recommended_pipeline": "local_ocr",
  "confidence": 72.5,
  "estimated_cost_brl": 0.004
}
```

### POST /pipeline/process
Processa documento usando pipeline em cascata.

**Request:** Form-data com arquivo + query param `force_pipeline` (opcional)

**Response:**
```json
{
  "success": true,
  "pipeline_used": "local_ocr",
  "stages_executed": ["quality_check", "local_ocr", "ai_analysis", "completed"],
  "processing_time_seconds": 5.2,
  "cost_estimate_brl": 0.004,
  "data": {
    "servicos": [...],
    "contratante": "..."
  }
}
```

### GET /pipeline/cost-estimate
Estima custo de processamento.

**Query params:** `num_pages`, `quality`

**Response:**
```json
{
  "num_pages": 10,
  "quality": "hard",
  "pipeline": "cloud_ocr",
  "total_cost_brl": 0.11
}
```

## Arquivos Criados

```
backend/services/
├── image_preprocessor.py    # Pré-processamento de imagem (deskew, contraste, ruído)
├── quality_detector.py      # Detector de qualidade de documentos
├── azure_document_service.py # Integração com Azure Document Intelligence
└── cascade_pipeline.py      # Orquestrador do pipeline em cascata

backend/routers/
└── pipeline_status.py       # Endpoints da API
```

## Níveis de Qualidade

| Nível | Descrição | Pipeline | Custo |
|-------|-----------|----------|-------|
| `native` | PDF com texto selecionável | pdfplumber + GPT-4o-mini | R$ 0.002 |
| `easy` | Escaneado com boa qualidade | EasyOCR + GPT-4o-mini | R$ 0.002 |
| `medium` | Escaneado com qualidade média | EasyOCR + GPT-4o-mini | R$ 0.002 |
| `hard` | Escaneado com baixa qualidade | Azure Read + GPT-4o-mini | R$ 0.011 |
| `very_hard` | Muito degradado/manuscrito | GPT-4o Vision | R$ 0.10 |

## Uso Programático

```python
from services.cascade_pipeline import cascade_pipeline

# Processar documento
result = cascade_pipeline.process("caminho/do/arquivo.pdf")

if result.success:
    print(f"Pipeline usado: {result.pipeline_used.value}")
    print(f"Custo: R$ {result.cost_estimate}")
    print(f"Serviços extraídos: {len(result.data.get('servicos', []))}")
else:
    print(f"Erros: {result.errors}")
```

## Economia Estimada

Para 1000 documentos com mix típico:

| Categoria | % | Pipeline | Custo |
|-----------|---|----------|-------|
| Fácil | 30% | pdfplumber + GPT-4o-mini | R$ 0.60 |
| Médio | 40% | EasyOCR + GPT-4o-mini | R$ 0.80 |
| Difícil | 25% | Azure + GPT-4o-mini | R$ 2.75 |
| Muito Difícil | 5% | GPT-4o Vision | R$ 5.00 |
| **TOTAL** | | | **R$ 9.15** |

**Economia: ~91%** comparado a usar GPT-4o Vision para tudo.
