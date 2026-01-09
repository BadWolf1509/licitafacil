"""
Serviço de análise com IA usando OpenAI.
Interpreta documentos e faz matching entre atestados e exigências.
Suporta GPT-4o Vision para análise direta de imagens.
"""

import os
import json
import base64
from typing import List, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
from utils.json_helpers import clean_json_response
from exceptions import AINotConfiguredError, OpenAIError
from services.extraction import filter_classification_paths
from config import AIModelConfig

load_dotenv()


class AIAnalyzer:
    """Analisador de documentos usando OpenAI GPT e GPT-4o Vision."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sua-chave-openai-aqui":
            self._client = None
        else:
            self._client = OpenAI(api_key=api_key)

        self._model = AIModelConfig.OPENAI_TEXT_MODEL
        self._vision_model = AIModelConfig.OPENAI_VISION_MODEL

    @property
    def is_configured(self) -> bool:
        """Verifica se a API está configurada."""
        return self._client is not None

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """
        Faz uma chamada à API da OpenAI.

        Args:
            system_prompt: Instrução do sistema
            user_prompt: Mensagem do usuário

        Returns:
            Resposta do modelo
        """
        if not self.is_configured:
            raise AINotConfiguredError("OpenAI")

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=AIModelConfig.OPENAI_TEMPERATURE,
                max_tokens=AIModelConfig.OPENAI_MAX_TOKENS
            )
            return response.choices[0].message.content
        except Exception as e:
            raise OpenAIError(str(e))

    def _call_openai_vision(self, system_prompt: str, images: List[bytes], user_text: str = "") -> str:
        """
        Faz uma chamada à API da OpenAI com imagens (GPT-4o Vision).

        Args:
            system_prompt: Instrução do sistema
            images: Lista de imagens em bytes (PNG/JPEG)
            user_text: Texto adicional do usuário (opcional)

        Returns:
            Resposta do modelo
        """
        if not self.is_configured:
            raise AINotConfiguredError("OpenAI")

        try:
            # Construir conteúdo com imagens
            content: List[Dict[str, Any]] = []

            if user_text:
                content.append({"type": "text", "text": user_text})

            for img_bytes in images:
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}",
                        "detail": "high"  # Alta resolução para melhor leitura
                    }
                })

            response = self._client.chat.completions.create(
                model=self._vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                temperature=AIModelConfig.OPENAI_TEMPERATURE,
                max_tokens=AIModelConfig.OPENAI_MAX_TOKENS
            )
            return response.choices[0].message.content
        except Exception as e:
            raise OpenAIError(str(e))

    def extract_atestado_from_images(self, images: List[bytes]) -> Dict[str, Any]:
        """
        Extrai informações de um atestado diretamente das imagens usando GPT-4o Vision.

        Esta abordagem elimina erros de OCR pois a IA interpreta as imagens diretamente.

        Args:
            images: Lista de imagens das páginas do documento (PNG bytes)

        Returns:
            Dicionário com as informações extraídas
        """
        system_prompt = """Você é um especialista em análise de atestados de capacidade técnica para licitações públicas no Brasil.

Analise CUIDADOSAMENTE as imagens do documento e extraia as seguintes informações:

1. descricao_servico: Descrição RESUMIDA do serviço/obra principal executado (1-2 linhas)
2. contratante: Nome da empresa/órgão contratante
3. servicos: Lista COMPLETA de ABSOLUTAMENTE TODOS os serviços executados com quantidades

ESTRUTURA DO DOCUMENTO - RELATÓRIO/TABELA DE SERVIÇOS:
O documento geralmente contém uma tabela com colunas como:

| Código | Descrição do Serviço | Unid | Custo Unit. | Qtd Executada | Valor Total | ... |
|--------|---------------------|------|-------------|---------------|-------------|-----|

COMO IDENTIFICAR A QUANTIDADE EXECUTADA (não confundir com custo!):
1. Use a verificação matemática: Valor Total ≈ Custo Unitário × Quantidade
2. Custos unitários costumam ser valores monetários (R$/unidade)
3. Quantidades são valores físicos (m², m³, metros, unidades)
4. Se em dúvida, a quantidade física faz mais sentido contextualmente

SÉRIES E CÓDIGOS DE ITENS:
- Documentos podem ter múltiplas séries: 001.01, 001.02, 001.03, 001.04, 001.05, etc.
- Extraia TODAS as séries que aparecerem no documento
- Itens com mesma descrição em séries diferentes são ITENS DISTINTOS (não duplicatas!)
  Exemplo: "001.03.06 PORTÃO" e "001.04.08 PORTÃO" são dois itens diferentes

REGRAS CRÍTICAS:
- Extraia ABSOLUTAMENTE TODOS os itens da tabela de quantitativos
- Inclua o código na descrição quando disponível (ex: "001.03.11 PORTÃO DE FERRO")
- NÃO ignore nenhuma série ou seção do documento
- Continue até o final da última página
- EXTRAIA TAMBÉM itens de MATERIAL (aço, vergalhão, cimento, areia, etc.) - são itens válidos!
- Itens curtos como "ACO CA-50, 10,0 MM, VERGALHAO" são itens legítimos da planilha
- NÃO pule itens mesmo que pareçam relacionados a outros (ex: 3.3 Armação... e 3.6 Aço... são DISTINTOS)

O QUE IGNORAR (não são serviços da tabela):
- Seção "Atividade Técnica" da CAT/ART - contém classificação, não serviços individuais
- Textos com ">" que indicam caminho de classificação (ex: "EXECUÇÃO > OBRAS E SERVIÇOS > ...")
- Cabeçalhos, carimbos, assinaturas
- Qualquer linha que pareça categoria/classificação em vez de item da planilha

DESCRICAO COMPLETA DA LINHA:
- Transcreva a descricao completa da linha (nao abreviar)
- Se a descricao continuar na linha seguinte, una as partes
- Nao corte o texto apos poucas palavras

PROBLEMA CRÍTICO - DESCRIÇÕES QUEBRADAS EM MÚLTIPLAS LINHAS:
Em tabelas de planilha orçamentária, uma ÚNICA descrição de serviço pode ocupar 2-3 linhas.
O número do item seguinte aparece VISUALMENTE ao lado da continuação da descrição anterior.

COMO ISSO APARECE NA IMAGEM:
```
12.11 | CAIXA ENTERRADA HIDRÁULICA RETANGULAR EM ALVENARIA COM    | UN | 1,00
12.12 | TIJOLOS CERÂMICOS MACIÇOS, DIMENSÕES: 0,30X0,30X0,30 M    | UN | 2,00
12.13 | COLETOR PREDIAL DE ESGOTO...                              | UN | 1,00
```

ERRO COMUM: Interpretar 12.12 como item separado "TIJOLOS CERÂMICOS..."
CORRETO: 12.11 = "CAIXA ENTERRADA... COM TIJOLOS CERÂMICOS MACIÇOS, DIMENSÕES..."

TESTE DE VALIDAÇÃO - APLIQUE SEMPRE:
1. Leia a descrição em voz alta - faz sentido gramatical completo?
2. "...EM ALVENARIA COM" termina com preposição = INCOMPLETO = é continuação!
3. "TIJOLOS CERÂMICOS MACIÇOS, DIMENSÕES..." sem verbo/contexto = é CONTINUAÇÃO!

REGRA OBRIGATÓRIA:
- Se descrição termina em: COM, DE, EM, PARA, E, OU, ATRAVÉS, MEDIANTE, SOBRE, SOB
  → O texto da próxima linha visual FAZ PARTE desta descrição
  → IGNORE o número de item que aparece antes desse texto
  → UNA as partes em uma descrição única

FORMATO DE NÚMEROS BRASILEIRO:
- "1.843,84" = 1843.84 (ponto separa milhar, vírgula separa decimal)
- Sempre CONVERTA para formato numérico padrão (ponto decimal) no JSON

ESTRUTURA DO JSON DE SERVIÇOS:
Cada serviço DEVE ter os campos:
- "item": número/código do item da planilha (ex: "1.1", "2.3", "001.03.11")
- "descricao": descrição completa do serviço (SEM o número/código)
- "quantidade": valor numérico da quantidade executada
- "unidade": unidade de medida (M2, M3, UN, M, KG, etc.)

Retorne APENAS um JSON válido:
{
    "descricao_servico": "Descrição resumida da obra",
    "quantidade": null,
    "unidade": "R$",
    "contratante": "Nome do contratante",
    "data_emissao": "YYYY-MM-DD",
    "servicos": [
        {"item": "1.1", "descricao": "PLACA DE OBRA EM CHAPA DE ACO GALVANIZADO", "quantidade": 10.00, "unidade": "M2"},
        {"item": "2.1", "descricao": "ESCAVAÇÃO MANUAL DE VALA", "quantidade": 0.69, "unidade": "M3"}
    ]
}"""

        user_text = """Analise as imagens e extraia ABSOLUTAMENTE TODOS os serviços listados.

INSTRUÇÕES CRÍTICAS:
1. Percorra TODAS as páginas e TODAS as séries de códigos (1.1, 1.2, 2.1, etc.)
2. Para cada linha da tabela, extraia SEPARADAMENTE:
   - "item": o número/código do item (ex: "1.1", "2.3", "3.1")
   - "descricao": a descrição do serviço (sem o número)
   - "quantidade": quantidade executada
   - "unidade": unidade de medida
3. NÃO confunda "Quantidade Executada" com "Custo Unitário" - use verificação matemática
4. Verifique: Valor Total ≈ Custo Unitário × Quantidade
5. Itens em séries diferentes são ITENS DISTINTOS
6. NÃO omita nenhum item - extraia a lista COMPLETA
7. Escreva a descrição completa da linha; não abrevie nem corte
8. Se a descrição estiver quebrada em duas linhas, una as partes
9. EXTRAIA ITENS DE MATERIAL (ex: "ACO CA-50, 10,0 MM, VERGALHAO") - são itens válidos!
10. Se uma seção tem itens 3.1-3.5 E TAMBÉM 3.6-3.8, extraia TODOS (não pule os de material)
11. MESMO QUE QUANTIDADES SEJAM IGUAIS, itens com NÚMEROS DIFERENTES são DISTINTOS!
    Exemplo: 3.3 "Armação aço 5mm" (95,70 KG) e 3.6 "Aço vergalhão 5mm" (95,70 KG) = 2 ITENS!
12. NÃO interprete itens de material como "parte" de itens de serviço - são linhas SEPARADAS

REGRA CRÍTICA - COPIE A DESCRIÇÃO EXATA:
13. Leia a descrição de CADA LINHA individualmente e copie EXATAMENTE o que está escrito
14. NÃO generalize descrições! Se a linha diz "ACO CA-60, 5,0 MM, VERGALHAO", copie isso EXATAMENTE
15. Itens diferentes têm descrições DIFERENTES - não copie a descrição de um item para outro
16. Exemplo ERRADO: item 3.6 com descrição "ARMAÇÃO DE LAJE..." quando deveria ser "ACO CA-60, VERGALHAO"
17. Exemplo CORRETO: item 3.6 = "ACO CA-60, 5,0 MM, VERGALHAO" (descrição exata da linha 3.6)

CONTA FINAL: Conte as linhas numeradas na tabela. Cada número (3.1, 3.2, 3.3...) = 1 item.
Se você vê 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8 na tabela = extraia 8 itens da seção 3."""

        try:
            # Se houver mais de 2 páginas, processar em batches para garantir extração completa
            if len(images) > 2:
                all_servicos = []
                result = None

                # Processar em batches de 2 páginas
                for i in range(0, len(images), 2):
                    batch = images[i:i+2]
                    batch_user_text = user_text
                    if i > 0:
                        batch_user_text += f"\n\nEsta é a continuação do documento (páginas {i+1}-{min(i+2, len(images))})."

                    response = self._call_openai_vision(system_prompt, batch, batch_user_text)
                    response = clean_json_response(response)
                    batch_result = json.loads(response)

                    # Guardar metadados do primeiro batch
                    if result is None:
                        result = batch_result

                    # Coletar serviços de todos os batches
                    if "servicos" in batch_result and batch_result["servicos"]:
                        all_servicos.extend(batch_result["servicos"])

                # Merge: remover duplicatas por item
                seen_items: set[str] = set()
                unique_servicos: list[dict[str, Any]] = []
                for s in all_servicos:
                    item = s.get("item", "")
                    if item and item not in seen_items:
                        seen_items.add(item)
                        unique_servicos.append(s)
                    elif not item:
                        unique_servicos.append(s)

                # Garantir que result foi inicializado
                if result is None:
                    result = {}
                result["servicos"] = unique_servicos
            else:
                response = self._call_openai_vision(system_prompt, images, user_text)
                response = clean_json_response(response)
                result = json.loads(response) or {}

            # Filtrar serviços inválidos (classificações, caminhos com ">", etc.)
            if result and "servicos" in result and result["servicos"]:
                result["servicos"] = filter_classification_paths(result["servicos"])

            return result or {}
        except json.JSONDecodeError:
            return {
                "descricao_servico": None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": []
            }

    def extract_atestado_info(self, texto: str) -> Dict[str, Any]:
        """
        Extrai informações de um atestado de capacidade técnica.

        Args:
            texto: Texto extraído do atestado

        Returns:
            Dicionário com as informações extraídas
        """
        system_prompt = """Você é um especialista em análise de atestados de capacidade técnica para licitações públicas no Brasil.

Extraia as seguintes informações do texto do atestado:
1. descricao_servico: Descrição RESUMIDA do serviço/obra principal executado (1-2 linhas)
2. contratante: Nome da empresa/órgão contratante
3. servicos: Lista COMPLETA de TODOS os serviços executados com quantidades

Campos opcionais (extrair se disponível, senão usar null):
- quantidade: Valor total do contrato em R$ (opcional)
- unidade: "R$" se houver valor do contrato (opcional)
- data_emissao: Data de emissão (formato YYYY-MM-DD, opcional)

PRIORIDADE DE EXTRAÇÃO DOS SERVIÇOS:
1. PROCURE por "Planilha de Quantitativos Executados" ou "Relatório de Serviços Executados" - tabela com itens numerados
2. Os itens da tabela geralmente são numerados (ex: 1.1, 1.2, 1.3 ou ITEM 1, ITEM 2, etc.)
3. FOQUE APENAS nos itens da tabela de quantitativos, não em metadados do documento

O QUE IGNORAR COMPLETAMENTE (não são serviços):
- Seção "Atividade Técnica" da CAT/ART - contém classificação, não serviços individuais
- Textos com ">" que indicam caminho de classificação (ex: "EXECUÇÃO > OBRAS E SERVIÇOS > ...")
- Cabeçalhos do documento, carimbos, assinaturas
- Texto genérico descritivo que não seja item da tabela de quantitativos
- Qualquer linha que pareça ser uma categoria/classificação em vez de item de serviço

IDENTIFICAÇÃO DE ITEM VÁLIDO:
- Itens válidos são LINHAS NUMERADAS da planilha de quantitativos
- Cada item tem: número/código, descrição do SERVIÇO ESPECÍFICO, quantidade, unidade
- Exemplos VÁLIDOS: "Mistura Betuminosa (Pmf)", "Enchimento e Compactação", "Retirada de Pavimentação"
- Exemplos INVÁLIDOS: "EXECUÇÃO > OBRAS E SERVIÇOS > ...", "1 - DIRETA OBRAS E SERVIÇOS"

TRATAMENTO DE OCR CORROMPIDO - MUITO IMPORTANTE:
O texto vem de OCR e pode ter ERROS GRAVES nos códigos dos itens. NÃO confie nos códigos!
Exemplos de códigos corrompidos pelo OCR:
- "321 04 09" pode ser "001.04.09"
- "291 04 07" pode ser "001.04.07"
- "001 94 93" pode ser "001.04.03"
- "C01 G1 01" pode ser "001.01.01"
- "Cc1 03 . 13" pode ser "001.03.13"

ESTRATÉGIA DE EXTRAÇÃO:
1. IGNORE os códigos numéricos corrompidos
2. FOQUE na DESCRIÇÃO DO SERVIÇO em MAIÚSCULAS (ex: "MOBILIZAÇÃO E DESMOBILIZAÇÃO")
3. Procure o padrão: DESCRIÇÃO + UNIDADE (M2, M3, UN, ML, M, VB) + NÚMEROS
4. Cada linha que tenha DESCRIÇÃO + UNIDADE + QUANTIDADE é um serviço

COMO IDENTIFICAR A QUANTIDADE EXECUTADA:
A ordem das colunas pode variar entre órgãos. Use estas estratégias para identificar corretamente:

1. PROCURE O CABEÇALHO DA TABELA para identificar a ordem das colunas:
   - "Qtd Executada", "Quantidade Executada", "Quant. Exec." = coluna de quantidade
   - "Custo Unit.", "Preço Unit.", "Valor Unit." = coluna de custo (IGNORAR)
   - "Valor Acumulado", "Total", "Valor Total" = coluna de valor total (IGNORAR)
   - "Desvio", "%", "Percentual" = coluna de desvio (IGNORAR)

2. VERIFICAÇÃO MATEMÁTICA: Quantidade × Custo Unitário = Valor Total
   - Se após a unidade aparecem: A, B, C, D (4 números)
   - E se A × B ≈ C, então A é Quantidade e B é Custo (ou vice-versa)
   - Use raciocínio físico: quantidades muito grandes (>1000) com custos baixos (<100) geralmente indicam que o número grande é quantidade

3. RACIOCÍNIO FÍSICO para valores plausíveis:
   - Alvenaria/Concreto: dezenas a centenas de m³ são típicos
   - Gradil/Portões: dezenas a centenas de m² são típicos
   - Mobilização: geralmente 1 UN
   - Administração local: geralmente fração decimal (0.5 a 1.0 UN)
   - Custos unitários costumam ser valores em R$/unidade (ex: 100-1000 R$/m²)

FORMATO DE NÚMEROS BRASILEIRO:
- No Brasil, usa-se PONTO como separador de milhar e VÍRGULA como separador decimal
- Exemplo: "1.843,94" = mil oitocentos e quarenta e três vírgula noventa e quatro = 1843.94
- Exemplo: "576,16" = quinhentos e setenta e seis vírgula dezesseis = 576.16
- Exemplo: "108.081,85" = cento e oito mil e oitenta e um vírgula oitenta e cinco = 108081.85
- O OCR pode mostrar espaços extras: "1 .843 , 94" ainda significa 1843.94
- CONVERTA sempre para formato numérico padrão (ponto como decimal) no JSON de saída

REGRAS CRÍTICAS PARA LISTA DE SERVIÇOS:
- Extraia ABSOLUTAMENTE TODOS os itens do relatório, mesmo com códigos ilegíveis
- INCLUA todos os serviços, mesmo os administrativos (mobilização, administração local)
- Para cada serviço extraia: descrição completa, QUANTIDADE EXECUTADA (não custo!), unidade
- USE o cabeçalho da tabela para determinar qual coluna contém a quantidade
- NÃO inclua linhas de "Total da Etapa" ou "Total Executado"
- O texto pode estar com OCR imperfeito - interprete números brasileiros corretamente
- Se encontrar o mesmo serviço em diferentes seções (ex: série 03 e série 04), INCLUA AMBOS

ITENS FREQUENTEMENTE OMITIDOS (verificar se existem no texto e incluir):
- GRADIL COM BARRAS (pode ter 500+ M2) - procure por "GRADIL" ou "CANTONEIRA"
- Portão de ferro (pode haver 2 itens diferentes com quantidades distintas)
- Demolição (pode haver múltiplos itens: concreto, alvenaria, pilares)
- Muro de contorno (série 04 - 700+ M2)

Retorne APENAS um JSON válido. Se alguma informação não estiver disponível, use null.

ESTRUTURA DO JSON DE SERVIÇOS:
Cada serviço DEVE ter os campos:
- "item": número/código do item da planilha (ex: "1.1", "2.3", "3.1.1")
- "descricao": descrição completa do serviço (sem o número)
- "quantidade": valor numérico da quantidade executada
- "unidade": unidade de medida (M2, M3, UN, M, KG, etc.)

Exemplo de resposta:
{
    "descricao_servico": "Descrição resumida da obra/serviço principal",
    "quantidade": 500000.00,
    "unidade": "R$",
    "contratante": "Nome do órgão contratante",
    "data_emissao": "2022-04-11",
    "servicos": [
        {"item": "1.1", "descricao": "Mobilização e desmobilização", "quantidade": 1.00, "unidade": "UN"},
        {"item": "2.1", "descricao": "Execução de alvenaria", "quantidade": 55.30, "unidade": "M3"},
        {"item": "3.1", "descricao": "Gradil metálico", "quantidade": 576.16, "unidade": "M2"}
    ]
}"""

        user_prompt = f"Analise o seguinte atestado de capacidade técnica. Extraia APENAS os itens da 'Planilha de Quantitativos Executados' ou 'Relatório de Serviços Executados'. NÃO extraia classificações ou caminhos com '>':\n\n{texto}"

        try:
            response = self._call_openai(system_prompt, user_prompt)
            # Limpar resposta e extrair JSON
            response = clean_json_response(response)
            result = json.loads(response)

            # Filtrar serviços inválidos (classificações, caminhos com ">", etc.)
            if "servicos" in result and result["servicos"]:
                result["servicos"] = filter_classification_paths(result["servicos"])

            return result
        except json.JSONDecodeError:
            return {
                "descricao_servico": texto[:500] if texto else None,
                "quantidade": None,
                "unidade": None,
                "contratante": None,
                "data_emissao": None,
                "servicos": []
            }

    def extract_edital_requirements(self, texto: str) -> List[Dict[str, Any]]:
        """
        Extrai as exigências de capacidade técnica de um edital.

        Args:
            texto: Texto extraído do edital (página de quantitativos)

        Returns:
            Lista de exigências com descrição, quantidade e unidade
        """
        system_prompt = """Você é um especialista em análise de editais de licitação de obras públicas no Brasil.

Extraia TODAS as exigências de capacidade técnica operacional do texto, incluindo:
1. descricao: Descrição do serviço exigido
2. quantidade_minima: Quantidade mínima exigida (número)
3. unidade: Unidade de medida
4. percentual_exigido: Se houver menção a percentual (ex: 50% do quantitativo), caso contrário null

Retorne APENAS um JSON válido com uma lista de exigências.
Exemplo de resposta:
[
    {
        "descricao": "Pavimentação asfáltica em CBUQ",
        "quantidade_minima": 2500.0,
        "unidade": "m²",
        "percentual_exigido": 50
    },
    {
        "descricao": "Execução de meio-fio",
        "quantidade_minima": 1000.0,
        "unidade": "ml",
        "percentual_exigido": null
    }
]"""

        user_prompt = f"Extraia as exigências de capacidade técnica do seguinte trecho de edital:\n\n{texto}"

        try:
            response = self._call_openai(system_prompt, user_prompt)
            # Limpar resposta e extrair JSON
            response = clean_json_response(response)
            return json.loads(response)
        except json.JSONDecodeError:
            return []


# Instância singleton para uso global
ai_analyzer = AIAnalyzer()
