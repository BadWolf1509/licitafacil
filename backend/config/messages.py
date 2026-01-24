"""
Mensagens padronizadas do LicitaFacil.
"""


class Messages:
    """Mensagens de erro e sucesso padronizadas."""
    # Recursos nao encontrados
    NOT_FOUND = "Recurso nao encontrado"
    ATESTADO_NOT_FOUND = "Atestado nao encontrado"
    ANALISE_NOT_FOUND = "Analise nao encontrada"
    USER_NOT_FOUND = "Usuario nao encontrado"
    JOB_NOT_FOUND = "Job nao encontrado"
    FILE_NOT_FOUND = "Arquivo nao encontrado"
    ATESTADO_FILE_NOT_FOUND = "Arquivo do atestado nao encontrado"
    EDITAL_FILE_NOT_FOUND = "Arquivo do edital nao encontrado"
    # Valores padrao
    DESCRICAO_NAO_IDENTIFICADA = "Descricao nao identificada"
    # Acesso e autenticacao
    ACCESS_DENIED = "Acesso negado"
    UNAUTHORIZED = "Acesso nao autorizado"
    FORBIDDEN = "Acesso proibido"
    CANNOT_DEACTIVATE_SELF = "Voce nao pode desativar sua propria conta"
    EMAIL_EXISTS = "Email ja cadastrado"
    INVALID_CREDENTIALS = "Email ou senha incorretos"
    USER_INACTIVE = "Usuario inativo"
    USER_NOT_APPROVED = "Usuario aguardando aprovacao do administrador"
    JOB_INVALID_STATUS = "Job nao pode ser processado no status atual"
    # Validacao de arquivos
    INVALID_FILE = "Arquivo invalido"
    INVALID_EXTENSION = "Extensao de arquivo nao permitida"
    FILE_REQUIRED = "Arquivo e obrigatorio"
    # Rate limiting e erros
    RATE_LIMIT_EXCEEDED = "Muitas requisicoes. Tente novamente em alguns minutos."
    INTERNAL_ERROR = "Erro interno do servidor"
    DB_ERROR = "Erro ao acessar o banco de dados"
    DUPLICATE_ENTRY = "Registro ja existe"
    PROCESSING_ERROR = "Erro ao processar documento. Tente novamente."
    QUEUE_ERROR = "Erro ao enfileirar processamento. Tente novamente."
    # Atestados
    NO_ATESTADOS = "Voce nao possui atestados cadastrados. Cadastre atestados antes de analisar uma licitacao."
    UPLOAD_SUCCESS = "Arquivo enviado. Processamento iniciado."
    ATESTADO_DELETED = "Atestado excluido com sucesso!"
    ANALISE_DELETED = "Analise excluida com sucesso!"
