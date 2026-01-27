# Arquitetura do Backend LicitaFácil

## Visão Geral

O backend do LicitaFácil é responsável pelo processamento de documentos de licitação,
extração de informações de atestados de capacidade técnica e editais, e matching
entre exigências e atestados disponíveis.

## Estrutura de Diretórios

```
backend/
├── config/                    # Configurações
│   ├── atestado.py           # Parâmetros de processamento
│   └── ...
├── docs/                      # Documentação
│   └── architecture.md       # Este arquivo
├── prompts/                   # Prompts de IA
│   ├── atestado_*.txt        # Prompts para atestados
│   ├── edital_*.txt          # Prompts para editais
│   └── __init__.py           # Funções de carregamento
├── services/                  # Serviços de negócio
│   ├── ai/                   # Serviços de IA unificados
│   ├── aditivo/              # Processamento de aditivos (NOVO)
│   ├── extraction/           # Módulos de extração
│   ├── processors/           # Processadores especializados
│   ├── providers/            # Provedores de IA
│   └── table_extraction/     # Extração de tabelas (NOVO)
├── tests/                     # Testes automatizados
└── utils/                     # Utilitários
```

## Módulos Principais

### services/extraction/ - Módulos de Extração

**Propósito**: Funções puras para processamento de dados extraídos.

| Módulo | Responsabilidade |
|--------|------------------|
| `constants.py` | Constantes centralizadas (categorias, tokens, unidades) |
| `patterns.py` | Padrões regex compilados |
| `item_utils.py` | Utilitários para códigos de item |
| `text_normalizer.py` | Normalização de texto, descrições, unidades |
| `table_processor.py` | Processamento de tabelas extraídas |
| `service_filter.py` | Filtragem e deduplicação de serviços |
| `quality_assessor.py` | Avaliação de qualidade da extração |

**Funções principais**:
```python
from services.extraction import (
    # Constantes
    KNOWN_CATEGORIES,
    SECTION_HEADERS,
    VALID_UNITS,
    # Normalização
    normalize_description,
    normalize_unit,
    # Parsing
    parse_item_tuple,
    parse_quantity,
    # Item utils
    normalize_item_code,
    strip_restart_prefix,
    split_restart_prefix,
    item_code_in_text,
)
```

### services/aditivo/ - Processamento de Aditivos

**Propósito**: Detectar e processar seções de aditivos contratuais em atestados.

| Módulo | Responsabilidade |
|--------|------------------|
| `detector.py` | Detecção de seções de aditivo via reinício de numeração |
| `validators.py` | Validação de linhas e descrições |
| `extractors.py` | Extração de informações de itens de aditivo |
| `transformer.py` | Transformação e prefixação de itens (FASE 1-3) |

**Uso**:
```python
from services.aditivo import (
    detect_aditivo_sections,  # Detecta seções de aditivo
    prefix_aditivo_items,     # Prefixa itens com S1-, S2-, AD-
    is_contaminated_line,     # Verifica se linha é ruído
    is_good_description,      # Valida qualidade de descrição
)
```

### services/table_extraction/ - Extração de Tabelas

**Propósito**: Extrair serviços de tabelas em documentos PDF.

```
table_extraction/
├── cascade.py           # CascadeStrategy - fluxo de extração em cascata
├── parsers/             # Parsing de texto
│   ├── text_parser.py   # parse_unit_qty_from_text, find_unit_qty_pairs
│   └── row_parser.py    # parse_row_text_to_servicos
├── filters/             # Filtros de ruído
│   └── row_filter.py    # is_row_noise, is_section_header_row, is_header_row
├── extractors/          # Extratores
│   ├── base.py          # ExtractionStrategy, ExtractionResult
│   ├── table.py         # TableExtractor class
│   ├── helpers.py       # extract_hidden_item, infer_missing_units
│   ├── ocr_helpers.py   # build_table_from_ocr_words, extract_from_ocr_words
│   ├── pdfplumber.py    # extract_servicos_from_tables
│   ├── document_ai.py   # extract_servicos_from_document_ai
│   ├── grid_ocr.py      # extract_servicos_from_grid_ocr
│   └── ocr_layout.py    # extract_servicos_from_ocr_layout
├── analyzers/           # Analisadores
│   └── document.py      # analyze_document_type
└── utils/               # Utilitários
    ├── planilha.py      # Gerenciamento de planilhas
    ├── merge.py         # Merge de fontes de tabela
    ├── quality.py       # calc_qty_ratio, calc_complete_ratio, calc_quality_metrics (fonte única)
    ├── pdf_render.py    # render_pdf_page, crop_page_image
    ├── grid_detect.py   # detect_grid_rows
    └── debug_utils.py   # summarize_table_debug
```

**Uso**:
```python
from services.table_extraction import (
    # Parsers
    parse_unit_qty_from_text,
    find_unit_qty_pairs,
    # Filters
    is_row_noise,
    is_section_header_row,
    strip_section_header_prefix,
    # Extractors
    TableExtractor,
    infer_missing_units,
    # Quality
    calc_qty_ratio,
    calc_complete_ratio,
)
```

### services/ai/ - Serviços de IA Unificados

**Propósito**: Centralizar toda lógica de extração via IA.

| Módulo | Responsabilidade |
|--------|------------------|
| `extraction_service.py` | Serviço unificado de extração (atestados, editais) |

**AIExtractionService** é a classe central que:
- Abstrai o provedor de IA (OpenAI, Gemini)
- Usa prompts externalizados do módulo `prompts/`
- Processa documentos multi-página em batches
- Filtra resultados inválidos

```python
from services.ai import extraction_service

# Extração de atestado via imagens
result = extraction_service.extract_atestado_from_images(images, provider=ai_provider)

# Extração de atestado via texto OCR
result = extraction_service.extract_atestado_info(texto, provider=ai_provider)

# Extração de requisitos de edital
requisitos = extraction_service.extract_edital_requirements(texto, provider=ai_provider)
```

### services/providers/ - Provedores de IA

**Propósito**: Implementações específicas de cada provedor.

| Módulo | Responsabilidade |
|--------|------------------|
| `openai_provider.py` | Integração com OpenAI (GPT-4, GPT-4o Vision) |
| `gemini_provider.py` | Integração com Google Gemini |

Todos implementam `BaseAIProvider`:
- `generate_text(system_prompt, user_prompt)` - Geração de texto
- `generate_with_vision(system_prompt, images, user_text)` - Análise de imagens

### services/processors/ - Processadores Especializados

**Propósito**: Classes extraídas do DocumentProcessor para modularização.

| Módulo | Responsabilidade |
|--------|------------------|
| `text_processor.py` | Extração de itens a partir de texto |
| `deduplication.py` | Deduplicação de serviços (pares, prefixos, planilhas) |
| `service_merger.py` | Mesclagem de planilhas fragmentadas |
| `service_filter.py` | Filtros de validação (headers, quantidade, código) |

**TextProcessor** métodos principais:
- `extract_item_codes_from_text_lines()` - Extrai códigos de item
- `extract_items_from_text_lines()` - Extrai itens completos de linhas
- `extract_items_from_text_section()` - Extrai da seção "SERVICOS EXECUTADOS"
- `extract_quantities_from_text()` - Extrai quantidades para códigos conhecidos
- `backfill_quantities_from_text()` - Preenche quantidades faltantes

**ServiceDeduplicator** métodos principais:
- `remove_duplicate_pairs()` - Remove pares X.Y e X.Y.1
- `dedupe_by_restart_prefix()` - Remove duplicatas com prefixos S1-, S2-
- `dedupe_within_planilha()` - Remove duplicatas por código/planilha
- `dedupe_all()` - Aplica todas as estratégias

**ServiceMerger** métodos principais:
- `merge_fragmented()` - Mescla planilhas fragmentadas
- `normalize_prefixes()` - Normaliza prefixos de restart
- `merge_and_normalize()` - Executa ambas operações

**ServiceFilter** métodos principais:
- `filter_headers()` - Remove cabeçalhos de seção
- `filter_no_quantity()` - Remove itens sem quantidade
- `filter_no_code()` - Remove itens sem código válido
- `filter_all()` - Aplica todos os filtros

### services/ - Serviços de Alto Nível

| Módulo | Responsabilidade |
|--------|------------------|
| `document_processor.py` | Orquestrador principal de processamento |
| `atestado_processor.py` | Processamento específico de atestados |
| `edital_processor.py` | Processamento específico de editais |
| `matching_service.py` | Matching entre exigências e atestados |
| `table_extraction_service.py` | Extração de tabelas de PDFs |
| `aditivo_processor.py` | Wrapper de compatibilidade (delega para services/aditivo/) |
| `text_extraction_service.py` | Extração de texto de PDFs |
| `ai_provider.py` | Gerenciador de provedores de IA |
| `ocr_service.py` | Serviço de OCR |
| `pdf_extractor.py` | Extração de PDFs |

### prompts/ - Prompts de IA

**Propósito**: Externalizar prompts para facilitar manutenção.

| Arquivo | Uso |
|---------|-----|
| `atestado_vision_system.txt` | System prompt para visão de atestados |
| `atestado_vision_user.txt` | User prompt para visão de atestados |
| `atestado_text_system.txt` | System prompt para texto de atestados |
| `edital_requirements_system.txt` | System prompt para extração de editais |

```python
from prompts import get_atestado_vision_prompts, get_edital_prompt

prompts = get_atestado_vision_prompts()  # {"system": ..., "user": ...}
edital_prompt = get_edital_prompt()       # System prompt para editais
```

## Fluxo de Processamento

### Processamento de Atestado

```
1. Upload do PDF
   ↓
2. DocumentProcessor.process_atestado()
   ├── Extração de texto (pdf_extractor + ocr_service)
   ├── Extração de tabelas (table_extraction_service)
   ├── Análise com IA (AIExtractionService)
   ├── Processamento de aditivos (services/aditivo)
   ├── Enriquecimento via texto (TextProcessor)
   └── Deduplicação e filtragem (service_filter)
   ↓
3. Resultado: Lista de serviços com item, descrição, unidade, quantidade
```

### Processamento de Edital

```
1. Upload do PDF
   ↓
2. EditalProcessor.process()
   ├── Extração de texto
   └── Extração de requisitos (AIExtractionService)
   ↓
3. Resultado: Lista de exigências de capacidade técnica
```

### Matching

```
1. Exigências do edital + Atestados disponíveis
   ↓
2. MatchingService.match_exigencias()
   ├── Normalização de descrições
   ├── Cálculo de similaridade
   └── Soma de quantidades por atestado
   ↓
3. Resultado: Mapa de exigência → atestados que atendem
```

## Padrões Arquiteturais

### Modularização por Pacotes

Os módulos grandes foram decompostos em pacotes menores:
- `aditivo_processor.py` (1141 → 21 linhas) → `services/aditivo/` (5 módulos)
- `table_extraction_service.py` (2894 → 353 linhas) → `services/table_extraction/` (25 módulos)

### Injeção de Dependência

```python
class AIExtractionService:
    def __init__(self, provider: Optional[BaseAIProvider] = None):
        self._provider = provider

    def extract_atestado_from_images(self, images, provider=None):
        ai = provider or self.provider  # Permite override por chamada
```

### Helpers Puros

```python
# Funções sem estado em módulos dedicados
from services.extraction.item_utils import normalize_item_code
from services.table_extraction.filters import is_row_noise
```

### Configuração Externalizada

```python
# config/atestado.py
class AtestadoProcessingConfig:
    RESTART_MIN_CODES = 10
    RESTART_MIN_OVERLAP = 3
    TEXT_SECTION_MAX_DESC_LEN = 500
```

## Métricas de Código

| Módulo | Linhas | Status |
|--------|--------|--------|
| `document_processor.py` | ~653 | Ativo (refatorado) |
| `table_extraction_service.py` | 304 | Ativo (wrapper limpo) |
| `aditivo_processor.py` | 21 | Ativo (wrapper com delegações) |
| `services/aditivo/` (pacote) | ~1200 | Ativo |
| `services/table_extraction/` (pacote) | ~2500 | Ativo |
| `services/extraction/` (pacote) | ~1100 | Ativo (expandido) |
| `services/processors/` (pacote) | ~1800 | Ativo (expandido) |

**Nota**: Refatoração concluída:
- `table_extraction_service.py`: 2894 → 304 linhas (-2590 linhas)
- `aditivo_processor.py`: 1141 → 21 linhas (-1120 linhas)
- `document_processor.py`: 1151 → 653 linhas (-498 linhas)
- `item_filters.py`: 670 → 46 linhas (wrapper de re-export)
- `text_processor.py`: 857 → 514 linhas (-343 linhas)
- `services/processors/`: Pacote com lógica extraída do DocumentProcessor
  - `deduplication.py`: ServiceDeduplicator (260 linhas)
  - `service_merger.py`: ServiceMerger (250 linhas)
  - `service_filter.py`: ServiceFilter (255 linhas)
  - `text_processor.py`: TextProcessor (514 linhas)
  - `text_cleanup.py`: Funções de limpeza de texto (207 linhas)
  - `text_line_parser.py`: Parser de linhas (351 linhas)
  - `text_section_builder.py`: Construtor de seções (233 linhas)
  - `quantity_extractor.py`: Extração de quantidades (280 linhas)
- `services/extraction/`: Módulos de validação e filtro
  - `validation_filters.py`: Filtros de validação (333 linhas)
  - `classification_filters.py`: Filtros de classificação (157 linhas)
  - `item_filters.py`: Re-exports para retrocompatibilidade (46 linhas)

## Testes Unitários

| Arquivo | Cobertura |
|---------|-----------|
| `tests/test_item_utils.py` | item_utils (29 testes) |
| `tests/test_patterns.py` | patterns.py (18 testes) |
| `tests/test_aditivo.py` | services/aditivo (17 testes) |
| `tests/test_table_extraction.py` | services/table_extraction (49 testes) |
| `tests/test_text_processor.py` | TextProcessor (29 testes) |
| `tests/test_sanitize_description.py` | sanitize_description (20 testes) |
| `tests/test_matching_service.py` | MatchingService (8 testes) |
| `tests/test_deduplication.py` | ServiceDeduplicator (26 testes) |
| `tests/test_service_merger.py` | ServiceMerger (15 testes) |
| `tests/test_service_filter.py` | ServiceFilter (23 testes) |

**Total**: 339 testes passando

## Convenções de Código

### Estrutura de Módulos

1. **Limite de Linhas**: Módulos devem ter no máximo ~500-800 linhas
2. **Responsabilidade Única**: Cada módulo tem uma responsabilidade clara
3. **Pacotes para Funcionalidades Complexas**: Agrupar módulos relacionados em pacotes

### Padrão de Re-export para Retrocompatibilidade

Ao refatorar módulos grandes, manter o módulo original como wrapper:

```python
# item_filters.py (wrapper)
"""
NOTA: Este módulo foi reorganizado. As funções foram movidas para:
- classification_filters.py: filter_classification_paths
- validation_filters.py: filter_servicos_by_item_length
"""
from .classification_filters import filter_classification_paths
from .validation_filters import filter_servicos_by_item_length
```

### Convenções de Naming

| Tipo | Convenção | Exemplo |
|------|-----------|---------|
| Módulos de filtro | `*_filters.py` | `validation_filters.py` |
| Módulos de parse | `*_parser.py` | `text_line_parser.py` |
| Módulos de extração | `*_extractor.py` | `quantity_extractor.py` |
| Módulos de limpeza | `*_cleanup.py` | `text_cleanup.py` |
| Classes principais | CamelCase | `TextProcessor` |
| Instâncias singleton | snake_case | `text_processor` |
| Funções privadas | `_prefixo` | `_build_description` |
| Constantes | UPPER_SNAKE | `STOP_PREFIXES` |

### Padrão Singleton

Classes com instância singleton para uso conveniente:

```python
class TextProcessor:
    """Processador de texto."""
    ...

# Instância singleton para uso conveniente
text_processor = TextProcessor()
```

### Organização de Imports

1. Stdlib primeiro
2. Dependências externas
3. Imports internos do projeto
4. Imports relativos do mesmo pacote

```python
import re
from typing import Dict, List, Optional

from config import AtestadoProcessingConfig
from services.extraction import normalize_unit, parse_quantity

from .text_cleanup import strip_trailing_unit_qty
```

### Testes

- Arquivos de teste em `tests/` seguem o padrão `test_<modulo>.py`
- Cada módulo público deve ter testes correspondentes
- Ao mover funções, atualizar imports nos testes
