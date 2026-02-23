"""Tests for Lembrete/Notificacao Pydantic schemas."""
from datetime import datetime

import pytest
from pydantic import ValidationError

from schemas.lembrete import (
    CalendarioQuery,
    LembreteCreate,
    LembreteResponse,
    LembreteStatusUpdate,
    LembreteUpdate,
    NotificacaoCountResponse,
    NotificacaoResponse,
    PreferenciaNotificacaoResponse,
    PreferenciaNotificacaoUpdate,
)

# ---------- LembreteCreate ----------

class TestLembreteCreate:

    def test_valid_minimal(self):
        data = LembreteCreate(
            titulo="Prazo de entrega",
            data_lembrete=datetime(2026, 3, 15, 10, 0),
        )
        assert data.titulo == "Prazo de entrega"
        assert data.tipo == "manual"
        assert data.canais == ["app"]

    def test_valid_full(self):
        data = LembreteCreate(
            titulo="Abertura licitacao",
            descricao="Lembrar de preparar documentos",
            data_lembrete=datetime(2026, 3, 15, 10, 0),
            data_evento=datetime(2026, 3, 20, 14, 0),
            tipo="abertura_licitacao",
            recorrencia="semanal",
            canais=["app", "email"],
            licitacao_id=1,
        )
        assert data.tipo == "abertura_licitacao"
        assert data.recorrencia == "semanal"
        assert data.canais == ["app", "email"]

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            LembreteCreate(descricao="Sem titulo nem data")

    def test_titulo_max_length(self):
        with pytest.raises(ValidationError):
            LembreteCreate(
                titulo="x" * 256,
                data_lembrete=datetime(2026, 3, 15),
            )

    def test_invalid_tipo(self):
        with pytest.raises(ValidationError, match="Tipo de lembrete inválido"):
            LembreteCreate(
                titulo="Teste",
                data_lembrete=datetime(2026, 3, 15),
                tipo="tipo_inexistente",
            )

    def test_invalid_recorrencia(self):
        with pytest.raises(ValidationError, match="Recorrência inválida"):
            LembreteCreate(
                titulo="Teste",
                data_lembrete=datetime(2026, 3, 15),
                recorrencia="bimestral",
            )

    def test_invalid_canal(self):
        with pytest.raises(ValidationError, match="Canal inválido"):
            LembreteCreate(
                titulo="Teste",
                data_lembrete=datetime(2026, 3, 15),
                canais=["sms"],
            )

    def test_all_valid_tipos(self):
        valid = [
            "manual", "abertura_licitacao", "encerramento_proposta",
            "vencimento_documento", "entrega_contrato", "prazo_recurso",
        ]
        for t in valid:
            data = LembreteCreate(
                titulo="Teste",
                data_lembrete=datetime(2026, 3, 15),
                tipo=t,
            )
            assert data.tipo == t

    def test_all_valid_recorrencias(self):
        for r in ["diario", "semanal", "mensal"]:
            data = LembreteCreate(
                titulo="Teste",
                data_lembrete=datetime(2026, 3, 15),
                recorrencia=r,
            )
            assert data.recorrencia == r


# ---------- LembreteUpdate ----------

class TestLembreteUpdate:

    def test_all_fields_optional(self):
        data = LembreteUpdate()
        assert data.titulo is None
        assert data.descricao is None

    def test_partial_update(self):
        data = LembreteUpdate(titulo="Novo titulo")
        assert data.titulo == "Novo titulo"
        assert data.data_lembrete is None


# ---------- LembreteStatusUpdate ----------

class TestLembreteStatusUpdate:

    def test_valid_status(self):
        data = LembreteStatusUpdate(status="enviado")
        assert data.status == "enviado"

    def test_invalid_status(self):
        with pytest.raises(ValidationError, match="Status de lembrete inválido"):
            LembreteStatusUpdate(status="inexistente")

    def test_all_valid_statuses(self):
        for s in ["pendente", "enviado", "lido", "cancelado"]:
            data = LembreteStatusUpdate(status=s)
            assert data.status == s


# ---------- LembreteResponse ----------

class TestLembreteResponse:

    def test_from_dict(self):
        now = datetime.now()
        data = LembreteResponse(
            id=1, user_id=1, titulo="Teste",
            data_lembrete=now, tipo="manual",
            status="pendente", created_at=now,
        )
        assert data.id == 1
        assert data.status == "pendente"


# ---------- NotificacaoResponse ----------

class TestNotificacaoResponse:

    def test_from_dict(self):
        now = datetime.now()
        data = NotificacaoResponse(
            id=1, user_id=1, titulo="Nova notificacao",
            mensagem="Voce tem um lembrete", tipo="lembrete",
            lida=False, created_at=now,
        )
        assert data.lida is False
        assert data.tipo == "lembrete"


class TestNotificacaoCountResponse:

    def test_valid(self):
        data = NotificacaoCountResponse(count=5)
        assert data.count == 5


# ---------- PreferenciaNotificacaoUpdate ----------

class TestPreferenciaNotificacaoUpdate:

    def test_all_optional(self):
        data = PreferenciaNotificacaoUpdate()
        assert data.email_habilitado is None

    def test_partial(self):
        data = PreferenciaNotificacaoUpdate(
            email_habilitado=False,
            antecedencia_horas=48,
        )
        assert data.email_habilitado is False
        assert data.antecedencia_horas == 48

    def test_antecedencia_min(self):
        with pytest.raises(ValidationError):
            PreferenciaNotificacaoUpdate(antecedencia_horas=0)

    def test_antecedencia_max(self):
        with pytest.raises(ValidationError):
            PreferenciaNotificacaoUpdate(antecedencia_horas=200)


# ---------- PreferenciaNotificacaoResponse ----------

class TestPreferenciaNotificacaoResponse:

    def test_from_dict(self):
        now = datetime.now()
        data = PreferenciaNotificacaoResponse(
            id=1, user_id=1, email_habilitado=True,
            app_habilitado=True, antecedencia_horas=24,
            email_resumo_diario=False, created_at=now,
        )
        assert data.antecedencia_horas == 24


# ---------- CalendarioQuery ----------

class TestCalendarioQuery:

    def test_valid(self):
        data = CalendarioQuery(
            data_inicio=datetime(2026, 2, 1),
            data_fim=datetime(2026, 2, 28),
        )
        assert data.data_inicio.month == 2
