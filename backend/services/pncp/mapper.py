"""Mapeamento entre dados PNCP e modelos do sistema."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from logging_config import get_logger

logger = get_logger("services.pncp.mapper")


class PncpMapper:
    """Mapeia dados da API PNCP para modelos internos."""

    @staticmethod
    def parse_pncp_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """Parseia datetime ISO 8601 da API PNCP."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_decimal(value: Any) -> Optional[Decimal]:
        """Converte valor para Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def extrair_resultado(
        item_pncp: Dict[str, Any],
        monitoramento_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Mapeia item da API PNCP para campos de PncpResultado."""
        orgao = item_pncp.get("orgaoEntidade", {}) or {}
        unidade = item_pncp.get("unidadeOrgao", {}) or {}

        return {
            "monitoramento_id": monitoramento_id,
            "user_id": user_id,
            "numero_controle_pncp": item_pncp.get("numeroControlePNCP", ""),
            "orgao_cnpj": orgao.get("cnpj"),
            "orgao_razao_social": orgao.get("razaoSocial"),
            "objeto_compra": item_pncp.get("objetoCompra"),
            "modalidade_nome": item_pncp.get("modalidadeNome"),
            "uf": unidade.get("ufSigla"),
            "municipio": unidade.get("municipioNome"),
            "valor_estimado": PncpMapper.parse_decimal(
                item_pncp.get("valorTotalEstimado"),
            ),
            "data_abertura": PncpMapper.parse_pncp_datetime(
                item_pncp.get("dataAberturaProposta"),
            ),
            "data_encerramento": PncpMapper.parse_pncp_datetime(
                item_pncp.get("dataEncerramentoProposta"),
            ),
            "link_sistema_origem": item_pncp.get("linkSistemaOrigem"),
            "dados_completos": item_pncp,
        }

    @staticmethod
    def resultado_para_licitacao(resultado: Any) -> Dict[str, Any]:
        """Mapeia PncpResultado para campos de criação de Licitação."""
        numero_controle = resultado.numero_controle_pncp or ""
        numero = f"PNCP-{numero_controle[-10:]}" if len(numero_controle) > 10 else f"PNCP-{numero_controle}"

        return {
            "numero": numero,
            "objeto": resultado.objeto_compra or "Sem descrição",
            "orgao": resultado.orgao_razao_social or "Não informado",
            "modalidade": resultado.modalidade_nome or "Não informada",
            "fonte": "pncp",
            "status": "identificada",
            "numero_controle_pncp": numero_controle,
            "valor_estimado": resultado.valor_estimado,
            "data_abertura": resultado.data_abertura,
            "data_encerramento": resultado.data_encerramento,
            "uf": resultado.uf,
            "municipio": resultado.municipio,
            "link_sistema_origem": resultado.link_sistema_origem,
            "observacoes": f"Importado do PNCP. Controle: {numero_controle}",
        }


    @staticmethod
    def item_pncp_para_licitacao(item: Dict[str, Any]) -> Dict[str, Any]:
        """Mapeia item cru da API PNCP diretamente para campos de Licitação."""
        orgao = item.get("orgaoEntidade", {}) or {}
        unidade = item.get("unidadeOrgao", {}) or {}
        numero_controle = item.get("numeroControlePNCP", "")
        numero = (
            f"PNCP-{numero_controle[-10:]}"
            if len(numero_controle) > 10
            else f"PNCP-{numero_controle}"
        )

        return {
            "numero": numero,
            "objeto": item.get("objetoCompra") or "Sem descrição",
            "orgao": orgao.get("razaoSocial") or "Não informado",
            "modalidade": item.get("modalidadeNome") or "Não informada",
            "fonte": "pncp",
            "status": "identificada",
            "numero_controle_pncp": numero_controle,
            "valor_estimado": PncpMapper.parse_decimal(
                item.get("valorTotalEstimado"),
            ),
            "data_abertura": PncpMapper.parse_pncp_datetime(
                item.get("dataAberturaProposta"),
            ),
            "data_encerramento": PncpMapper.parse_pncp_datetime(
                item.get("dataEncerramentoProposta"),
            ),
            "uf": unidade.get("ufSigla"),
            "municipio": unidade.get("municipioNome"),
            "link_sistema_origem": item.get("linkSistemaOrigem"),
            "observacoes": f"Importado do PNCP (busca direta). Controle: {numero_controle}",
        }


pncp_mapper = PncpMapper()
