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

load_dotenv()


class AIAnalyzer:
    """Analisador de documentos usando OpenAI GPT e GPT-4o Vision."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sua-chave-openai-aqui":
            self._client = None
        else:
            self._client = OpenAI(api_key=api_key)

        self._model = "gpt-4o-mini"  # Modelo para texto
        self._vision_model = "gpt-4o"  # Modelo com capacidade de visão

    @property
    def is_configured(self) -> bool:
        """Verifica se a API está configurada."""
        return self._client is not None

    def _filter_invalid_services(self, servicos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtra serviços inválidos da extração.

        Remove itens que são classificações/categorias em vez de serviços reais.

        Args:
            servicos: Lista de serviços extraídos

        Returns:
            Lista de serviços filtrada
        """
        if not servicos:
            return []

        filtered = []
        for servico in servicos:
            descricao = servico.get("descricao", "") or ""

            # Ignorar itens vazios
            if not descricao.strip():
                continue

            # Ignorar itens que contêm ">" (caminho de classificação)
            if ">" in descricao:
                continue

            # Ignorar itens que começam com padrão de classificação
            desc_upper = descricao.upper().strip()

            # Prefixos que SEMPRE indicam classificação (não serviços reais)
            invalid_prefixes = [
                "DIRETA OBRAS",
                "1 - DIRETA",
                "2 - DIRETA",
                "ATIVIDADE TÉCNICA",
                "CLASSIFICAÇÃO",
            ]
            is_invalid = False
            for prefix in invalid_prefixes:
                if desc_upper.startswith(prefix):
                    is_invalid = True
                    break

            # "EXECUÇÃO" é inválido APENAS se seguido de ">" (classificação)
            # mas é VÁLIDO se for serviço real como "EXECUÇÃO DE PAVIMENTO"
            if desc_upper.startswith("EXECUÇÃO") and ">" in desc_upper:
                is_invalid = True

            if is_invalid:
                continue

            # Ignorar itens muito curtos (provavelmente não são serviços reais)
            if len(descricao.strip()) < 5:
                continue

            filtered.append(servico)

        return filtered

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
            raise Exception("API OpenAI não configurada. Defina OPENAI_API_KEY no arquivo .env")

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,  # Zero para máxima consistência
                max_tokens=16000  # Aumentado para extrair todos os serviços detalhados
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Erro na API OpenAI: {str(e)}")

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
            raise Exception("API OpenAI não configurada. Defina OPENAI_API_KEY no arquivo .env")

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
                temperature=0,
                max_tokens=16000
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Erro na API OpenAI Vision: {str(e)}")

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

O QUE IGNORAR (não são serviços da tabela):
- Seção "Atividade Técnica" da CAT/ART - contém classificação, não serviços individuais
- Textos com ">" que indicam caminho de classificação (ex: "EXECUÇÃO > OBRAS E SERVIÇOS > ...")
- Cabeçalhos, carimbos, assinaturas
- Qualquer linha que pareça categoria/classificação em vez de item da planilha

DESCRICAO COMPLETA DA LINHA:
- Transcreva a descricao completa da linha (nao abreviar)
- Se a descricao continuar na linha seguinte, una as partes
- Nao corte o texto apos poucas palavras

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

CONTA FINAL: Ao terminar, verifique se extraiu todos os itens de todas as séries."""

        try:
            response = self._call_openai_vision(system_prompt, images, user_text)
            # Limpar resposta e extrair JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            result = json.loads(response.strip())

            # Filtrar serviços inválidos (classificações, caminhos com ">", etc.)
            if "servicos" in result and result["servicos"]:
                result["servicos"] = self._filter_invalid_services(result["servicos"])

            return result
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
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            result = json.loads(response.strip())

            # Filtrar serviços inválidos (classificações, caminhos com ">", etc.)
            if "servicos" in result and result["servicos"]:
                result["servicos"] = self._filter_invalid_services(result["servicos"])

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
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            return json.loads(response.strip())
        except json.JSONDecodeError:
            return []

    def match_atestados_to_requirements(
        self,
        requirements: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Faz o matching entre exigências do edital e atestados disponíveis.

        Args:
            requirements: Lista de exigências do edital
            atestados: Lista de atestados do usuário

        Returns:
            Lista de resultados com status de atendimento
        """
        system_prompt = """Você é um especialista em qualificação técnica para licitações públicas no Brasil.

Analise as exigências do edital e os atestados disponíveis. Para cada exigência:
1. Identifique quais atestados são compatíveis (mesmo tipo de serviço)
2. Verifique se a quantidade atende (soma dos atestados >= quantidade mínima exigida)
3. A soma de atestados é SEMPRE permitida conforme Art. 67 da Lei 14.133/2021

Retorne um JSON com o seguinte formato para cada exigência:
{
    "exigencia": "descrição da exigência",
    "quantidade_exigida": 1000.0,
    "unidade": "m²",
    "atestados_compativeis": [
        {"id": 1, "descricao": "...", "quantidade": 500.0}
    ],
    "quantidade_atendida": 750.0,
    "status": "atende" | "parcial" | "nao_atende",
    "percentual_atendido": 75.0,
    "observacao": "Sugestão ou observação"
}"""

        user_prompt = f"""EXIGÊNCIAS DO EDITAL:
{json.dumps(requirements, ensure_ascii=False, indent=2)}

ATESTADOS DISPONÍVEIS:
{json.dumps(atestados, ensure_ascii=False, indent=2)}

Faça o matching e retorne o resultado em JSON."""

        try:
            response = self._call_openai(system_prompt, user_prompt)
            # Limpar resposta e extrair JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            return json.loads(response.strip())
        except json.JSONDecodeError:
            # Retornar resultado básico sem IA
            return self._basic_matching(requirements, atestados)

    def _basic_matching(
        self,
        requirements: List[Dict[str, Any]],
        atestados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Matching básico sem IA (fallback).

        Usa comparação simples de strings para encontrar atestados compatíveis.
        """
        results = []

        for req in requirements:
            req_desc = req.get("descricao", "").lower()
            req_qty = req.get("quantidade_minima", 0) or 0
            req_unit = req.get("unidade", "")

            compatible = []
            total_qty = 0

            for at in atestados:
                at_desc = (at.get("descricao_servico") or "").lower()
                at_qty = at.get("quantidade", 0) or 0
                at_unit = at.get("unidade", "")

                # Verificar compatibilidade básica (palavras em comum)
                req_words = set(req_desc.split())
                at_words = set(at_desc.split())
                common_words = req_words & at_words

                # Se tiver palavras significativas em comum e mesma unidade
                significant_words = common_words - {"de", "do", "da", "em", "para", "com", "e", "a", "o"}
                if len(significant_words) >= 2 and (at_unit.lower() == req_unit.lower() or not at_unit):
                    compatible.append({
                        "id": at.get("id"),
                        "descricao": at.get("descricao_servico"),
                        "quantidade": at_qty
                    })
                    total_qty += at_qty

            # Calcular percentual e status
            percentual = (total_qty / req_qty * 100) if req_qty > 0 else 0
            if percentual >= 100:
                status = "atende"
            elif percentual >= 50:
                status = "parcial"
            else:
                status = "nao_atende"

            results.append({
                "exigencia": req.get("descricao"),
                "quantidade_exigida": req_qty,
                "unidade": req_unit,
                "atestados_compativeis": compatible,
                "quantidade_atendida": total_qty,
                "status": status,
                "percentual_atendido": round(percentual, 2),
                "observacao": None
            })

        return results


# Instância singleton para uso global
ai_analyzer = AIAnalyzer()
