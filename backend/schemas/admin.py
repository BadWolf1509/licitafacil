from pydantic import BaseModel


class AdminStatsResponse(BaseModel):
    """Estatísticas de usuários do sistema."""
    total_usuarios: int
    usuarios_aprovados: int
    usuarios_pendentes: int
    usuarios_inativos: int
