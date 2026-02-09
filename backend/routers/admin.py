from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from auth import get_current_admin_user
from config import Messages
from database import get_db
from models import Usuario
from repositories import usuario_repository
from routers.base import AdminRouter
from schemas import AdminStatsResponse, JobBulkDeleteResponse, JobCleanupResponse, Mensagem, PaginatedUsuarioResponse
from services.audit_service import AuditAction, audit_service
from services.cache import cached, invalidate_prefix
from services.processing_queue import processing_queue
from utils.http_helpers import get_client_ip_safe
from utils.pagination import PaginationParams, paginate_query

router = AdminRouter(prefix="/admin", tags=["Administração"])


@router.get(
    "/usuarios/pendentes",
    response_model=PaginatedUsuarioResponse,
    summary="Listar usuários pendentes",
    responses={
        200: {"description": "Lista de usuários pendentes"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
    }
)
def list_pending_users(
    pagination: PaginationParams = Depends(),
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> PaginatedUsuarioResponse:
    """
    Lista todos os usuários pendentes de aprovação com paginação.

    Retorna usuários que se registraram mas ainda não foram aprovados
    por um administrador.
    """
    query = db.query(Usuario).filter(
        Usuario.is_approved == False  # noqa: E712 - SQLAlchemy requires == for column comparison
    ).order_by(Usuario.created_at.desc())
    return paginate_query(query, pagination, PaginatedUsuarioResponse)


@router.get(
    "/usuarios",
    response_model=PaginatedUsuarioResponse,
    summary="Listar todos os usuários",
    responses={
        200: {"description": "Lista de usuários"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
    }
)
def list_all_users(
    pagination: PaginationParams = Depends(),
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> PaginatedUsuarioResponse:
    """
    Lista todos os usuários do sistema com paginação.

    Inclui usuários aprovados, pendentes, ativos e inativos.
    """
    query = db.query(Usuario).order_by(Usuario.created_at.desc())
    return paginate_query(query, pagination, PaginatedUsuarioResponse)


@router.post(
    "/usuarios/{user_id}/aprovar",
    response_model=Mensagem,
    summary="Aprovar usuário",
    responses={
        200: {"description": "Usuário aprovado com sucesso"},
        400: {"description": "Usuário já está aprovado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
        404: {"description": "Usuário não encontrado"},
    }
)
def approve_user(
    user_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Aprova um usuário pendente para uso do sistema.

    Após aprovação, o usuário poderá fazer login e acessar
    todas as funcionalidades disponíveis.
    """
    usuario = usuario_repository.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.USER_NOT_FOUND
        )

    if usuario.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já está aprovado"
        )

    usuario.is_approved = True
    usuario.approved_at = datetime.now(timezone.utc)
    usuario.approved_by = current_user.id
    db.commit()

    invalidate_prefix("admin_stats")

    # Registrar auditoria
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.USER_APPROVED,
        resource_type="usuario",
        resource_id=usuario.id,
        details={"email": usuario.email, "nome": usuario.nome},
        ip_address=get_client_ip_safe(request)
    )

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} aprovado com sucesso!",
        sucesso=True
    )


@router.post(
    "/usuarios/{user_id}/rejeitar",
    response_model=Mensagem,
    summary="Desativar usuário",
    responses={
        200: {"description": "Usuário desativado com sucesso"},
        400: {"description": "Não pode desativar a si mesmo"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
        404: {"description": "Usuário não encontrado"},
    }
)
def deactivate_user(
    user_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Desativa um usuário do sistema.

    Usuários desativados não conseguem fazer login.
    Esta ação pode ser revertida usando o endpoint de reativação.
    """
    usuario = usuario_repository.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.USER_NOT_FOUND
        )

    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.CANNOT_DEACTIVATE_SELF
        )

    usuario.is_active = False
    db.commit()

    invalidate_prefix("admin_stats")

    # Registrar auditoria
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.USER_DEACTIVATED,
        resource_type="usuario",
        resource_id=usuario.id,
        details={"email": usuario.email, "nome": usuario.nome},
        ip_address=get_client_ip_safe(request)
    )

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} desativado com sucesso!",
        sucesso=True
    )


@router.post(
    "/usuarios/{user_id}/reativar",
    response_model=Mensagem,
    summary="Reativar usuário",
    responses={
        200: {"description": "Usuário reativado com sucesso"},
        400: {"description": "Usuário já está ativo"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
        404: {"description": "Usuário não encontrado"},
    }
)
def reactivate_user(
    user_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Reativa um usuário que foi desativado.

    O usuário poderá fazer login novamente após a reativação.
    """
    usuario = usuario_repository.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.USER_NOT_FOUND
        )

    if usuario.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário já está ativo"
        )

    usuario.is_active = True
    db.commit()

    invalidate_prefix("admin_stats")

    # Registrar auditoria
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.USER_REACTIVATED,
        resource_type="usuario",
        resource_id=usuario.id,
        details={"email": usuario.email, "nome": usuario.nome},
        ip_address=get_client_ip_safe(request)
    )

    return Mensagem(
        mensagem=f"Usuário {usuario.nome} reativado com sucesso!",
        sucesso=True
    )


@router.delete(
    "/usuarios/{user_id}",
    response_model=Mensagem,
    summary="Excluir usuário",
    responses={
        200: {"description": "Usuário excluído permanentemente"},
        400: {"description": "Não pode excluir a si mesmo ou um administrador"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
        404: {"description": "Usuário não encontrado"},
    }
)
def delete_user(
    user_id: int,
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Exclui permanentemente um usuário do sistema.

    **ATENÇÃO:** Esta ação é irreversível. Todos os dados do usuário
    (atestados, análises, etc.) serão removidos permanentemente.

    Não é possível excluir administradores ou a própria conta.
    """
    usuario = usuario_repository.get_by_id(db, user_id)
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=Messages.USER_NOT_FOUND
        )

    if usuario.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível excluir sua própria conta"
        )

    if usuario.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível excluir um administrador"
        )

    nome = usuario.nome
    email = usuario.email
    deleted_user_id = usuario.id

    db.delete(usuario)
    db.commit()

    invalidate_prefix("admin_stats")

    # Registrar auditoria
    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.USER_DELETED,
        resource_type="usuario",
        resource_id=deleted_user_id,
        details={"email": email, "nome": nome},
        ip_address=get_client_ip_safe(request)
    )

    return Mensagem(
        mensagem=f"Usuário {nome} excluído permanentemente!",
        sucesso=True
    )


@router.get(
    "/estatisticas",
    response_model=AdminStatsResponse,
    summary="Obter estatísticas do sistema",
    responses={
        200: {"description": "Estatísticas retornadas"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
    }
)
def get_statistics(
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
) -> AdminStatsResponse:
    """
    Retorna estatísticas gerais do sistema.

    **Inclui:**
    - Total de usuários (ativos, inativos, pendentes)
    - Total de atestados cadastrados
    - Total de análises realizadas
    """
    return AdminStatsResponse(**_get_cached_stats(db))


@cached(ttl=60, prefix="admin_stats")
def _get_cached_stats(db: Session) -> dict:
    """Retorna estatisticas com cache de 60s."""
    return usuario_repository.get_stats(db)


@router.post(
    "/jobs/cleanup",
    response_model=JobCleanupResponse,
    summary="Limpar jobs órfãos",
    responses={
        200: {"description": "Jobs órfãos limpos com sucesso"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
    }
)
def cleanup_orphaned_jobs(
    request: Request,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> JobCleanupResponse:
    """
    Limpa jobs órfãos (arquivos ausentes) e stuck (em processamento sem worker).

    Marca esses jobs como FAILED para que não sejam reprocessados.
    Útil após reinícios do servidor ou limpeza de arquivos temporários.
    """
    result = processing_queue._repository.cleanup_orphaned_jobs()

    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.SYSTEM_CLEANUP,
        resource_type="jobs",
        details=result,
        ip_address=get_client_ip_safe(request)
    )

    return JobCleanupResponse(
        **result,
        message=f"{result['total_cleaned']} jobs limpos ({result['orphaned_files']} órfãos, {result['stuck_processing']} stuck)"
    )


@router.delete(
    "/jobs/failed",
    response_model=JobBulkDeleteResponse,
    summary="Remover todos os jobs falhados",
    responses={
        200: {"description": "Jobs falhados removidos"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
    }
)
def delete_failed_jobs(
    request: Request,
    include_cancelled: bool = False,
    current_user: Usuario = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> JobBulkDeleteResponse:
    """
    Remove permanentemente todos os jobs com status FAILED.

    **Parâmetros:**
    - `include_cancelled`: Se True, também remove jobs CANCELLED (padrão: False)
    """
    statuses = ['failed']
    if include_cancelled:
        statuses.append('cancelled')

    deleted = processing_queue._repository.delete_by_statuses(statuses)

    audit_service.log_action(
        db=db,
        user_id=current_user.id,
        action=AuditAction.SYSTEM_CLEANUP,
        resource_type="jobs",
        details={"deleted": deleted, "statuses": statuses},
        ip_address=get_client_ip_safe(request)
    )

    return JobBulkDeleteResponse(
        deleted=deleted,
        message=f"{deleted} jobs removidos permanentemente"
    )


@router.get(
    "/jobs/diagnostico",
    summary="Diagnóstico de conexão com banco de dados",
    responses={
        200: {"description": "Resultado do diagnóstico"},
        401: {"description": "Não autenticado"},
        403: {"description": "Não é administrador"},
    }
)
def diagnose_db_connection(
    current_user: Usuario = Depends(get_current_admin_user),
):
    """
    Testa a conexão com o banco de dados e verifica se operações CRUD funcionam.

    Cria um job de teste, verifica, exclui e verifica novamente.
    """
    import uuid

    from sqlalchemy import text

    from database import engine

    test_id = f"diag-{uuid.uuid4().hex[:8]}"
    steps: list[dict] = []
    results: dict = {"steps": steps, "success": False}

    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Step 1: Contar jobs atuais
            count_before = conn.execute(
                text("SELECT COUNT(*) FROM processing_jobs")
            ).scalar()
            steps.append({
                "step": "count_before",
                "value": count_before
            })

            # Step 2: Inserir job de teste
            conn.execute(
                text(
                    "INSERT INTO processing_jobs (id, user_id, file_path, job_type, status, created_at) "
                    "VALUES (:id, :uid, :fp, 'diagnostico', 'failed', :ts)"
                ),
                {"id": test_id, "uid": current_user.id, "fp": "/tmp/diag.pdf", "ts": datetime.now(timezone.utc).isoformat()}
            )
            steps.append({"step": "insert", "status": "ok"})

            # Step 3: Verificar se existe
            exists = conn.execute(
                text("SELECT id, status FROM processing_jobs WHERE id = :id"),
                {"id": test_id}
            ).fetchone()
            steps.append({
                "step": "verify_insert",
                "found": exists is not None,
                "data": {"id": exists[0], "status": exists[1]} if exists else None
            })

            # Step 4: Deletar
            del_result = conn.execute(
                text("DELETE FROM processing_jobs WHERE id = :id"),
                {"id": test_id}
            )
            steps.append({
                "step": "delete",
                "rowcount": del_result.rowcount
            })

            # Step 5: Verificar se foi deletado
            still_exists = conn.execute(
                text("SELECT COUNT(*) FROM processing_jobs WHERE id = :id"),
                {"id": test_id}
            ).scalar() or 0
            steps.append({
                "step": "verify_delete",
                "still_exists": still_exists > 0
            })

            # Step 6: Contar jobs finais
            count_after = conn.execute(
                text("SELECT COUNT(*) FROM processing_jobs")
            ).scalar()
            steps.append({
                "step": "count_after",
                "value": count_after
            })

            # Step 7: Listar IDs de jobs failed para referência
            failed_jobs = conn.execute(
                text("SELECT id, original_filename, status FROM processing_jobs WHERE status = 'failed' LIMIT 5")
            ).fetchall()
            steps.append({
                "step": "sample_failed_jobs",
                "jobs": [{"id": r[0], "filename": r[1], "status": r[2]} for r in failed_jobs]
            })

            results["success"] = not (still_exists > 0)
            results["diagnosis"] = (
                "DB DELETE funciona corretamente com AUTOCOMMIT"
                if results["success"]
                else "FALHA: DELETE não persistiu - verificar RLS ou permissões no Supabase"
            )

    except Exception as e:
        steps.append({"step": "error", "message": str(e)})
        results["diagnosis"] = f"Erro na conexão: {str(e)}"

    return results
