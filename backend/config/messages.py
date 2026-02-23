"""
Mensagens padronizadas do LicitaFácil.
"""


class Messages:
    """Mensagens de erro e sucesso padronizadas."""
    # Recursos não encontrados
    NOT_FOUND = "Recurso não encontrado"
    ATESTADO_NOT_FOUND = "Atestado não encontrado"
    ANALISE_NOT_FOUND = "Análise não encontrada"
    USER_NOT_FOUND = "Usuário não encontrado"
    JOB_NOT_FOUND = "Job não encontrado"
    FILE_NOT_FOUND = "Arquivo não encontrado"
    ATESTADO_FILE_NOT_FOUND = "Arquivo do atestado não encontrado"
    EDITAL_FILE_NOT_FOUND = "Arquivo do edital não encontrado"
    # Valores padrão
    DESCRICAO_NAO_IDENTIFICADA = "Descrição não identificada"
    # Acesso e autenticação
    ACCESS_DENIED = "Acesso negado"
    UNAUTHORIZED = "Acesso não autorizado"
    FORBIDDEN = "Acesso proibido"
    CANNOT_DEACTIVATE_SELF = "Você não pode desativar sua própria conta"
    EMAIL_EXISTS = "Email já cadastrado"
    INVALID_CREDENTIALS = "Email ou senha incorretos"
    USER_INACTIVE = "Usuário inativo"
    USER_NOT_APPROVED = "Usuário aguardando aprovação do administrador"
    JOB_INVALID_STATUS = "Job não pode ser processado no status atual"
    # Validação de arquivos
    INVALID_FILE = "Arquivo inválido"
    INVALID_EXTENSION = "Extensão de arquivo não permitida"
    FILE_REQUIRED = "Arquivo é obrigatório"
    # Rate limiting e erros
    RATE_LIMIT_EXCEEDED = "Muitas requisições. Tente novamente em alguns minutos."
    INTERNAL_ERROR = "Erro interno do servidor"
    DB_ERROR = "Erro ao acessar o banco de dados"
    DUPLICATE_ENTRY = "Registro já existe"
    PROCESSING_ERROR = "Erro ao processar documento. Tente novamente."
    QUEUE_ERROR = "Erro ao enfileirar processamento. Tente novamente."
    # Atestados
    NO_ATESTADOS = "Você não possui atestados cadastrados. Cadastre atestados antes de analisar uma licitação."
    UPLOAD_SUCCESS = "Arquivo enviado. Processamento iniciado."
    ATESTADO_DELETED = "Atestado excluído com sucesso!"
    ANALISE_DELETED = "Análise excluída com sucesso!"
    # Licitações
    LICITACAO_NOT_FOUND = "Licitação não encontrada"
    LICITACAO_DELETED = "Licitação excluída com sucesso!"
    LICITACAO_STATUS_UPDATED = "Status da licitação atualizado com sucesso!"
    INVALID_STATUS_TRANSITION = "Transição de status inválida"
    TAG_ALREADY_EXISTS = "Tag já existe nesta licitação"
    TAG_NOT_FOUND = "Tag não encontrada"
    # Lembretes
    LEMBRETE_NOT_FOUND = "Lembrete não encontrado"
    LEMBRETE_DELETED = "Lembrete excluído com sucesso!"
    LEMBRETE_STATUS_UPDATED = "Status do lembrete atualizado!"
    INVALID_LEMBRETE_STATUS = "Status de lembrete inválido"
    # Notificações
    NOTIFICACAO_NOT_FOUND = "Notificação não encontrada"
    NOTIFICACAO_DELETED = "Notificação excluída com sucesso!"
    TODAS_LIDAS = "Todas as notificações marcadas como lidas"
    PREFERENCIAS_ATUALIZADAS = "Preferências de notificação atualizadas"
    # Documentos
    DOCUMENTO_NOT_FOUND = "Documento não encontrado"
    DOCUMENTO_DELETED = "Documento excluído com sucesso!"
    DOCUMENTO_UPLOAD_SUCCESS = "Documento enviado com sucesso!"
    DOCUMENTO_FILE_REQUIRED = "Arquivo é obrigatório para upload"
    # Checklist
    CHECKLIST_ITEM_NOT_FOUND = "Item do checklist não encontrado"
    CHECKLIST_ITEM_DELETED = "Item do checklist excluído!"
    CHECKLIST_UPDATED = "Checklist atualizado com sucesso!"
    # PNCP
    PNCP_MONITOR_NOT_FOUND = "Monitoramento não encontrado"
    PNCP_MONITOR_DELETED = "Monitoramento excluído com sucesso!"
    PNCP_RESULTADO_NOT_FOUND = "Resultado PNCP não encontrado"
    PNCP_RESULTADO_JA_IMPORTADO = "Este resultado já foi importado como licitação"
    PNCP_SYNC_INICIADA = "Sincronização manual iniciada"
    PNCP_BUSCA_ERRO = "Erro ao buscar no PNCP. Tente novamente."
