// Configurações globais do LicitaFácil

// Detecta URL do backend automaticamente
// Em desenvolvimento: usa mesma origem
// Em produção (Vercel): usa BACKEND_URL definida ou proxy via rewrites
function getApiUrl() {
    // Se há variável global definida (injetada pelo build ou em env.js)
    if (typeof window.BACKEND_URL !== 'undefined' && window.BACKEND_URL) {
        return window.BACKEND_URL;
    }

    // Se está no Vercel (vercel.app ou domínio customizado com proxy configurado)
    // O vercel.json faz rewrite de /api/* para o backend
    return window.location.origin;
}

const CONFIG = {
    // URL base da API (detectada automaticamente)
    API_URL: getApiUrl(),

    // Prefixo de versão da API
    API_PREFIX: '/api/v1',

    // Chaves do localStorage
    TOKEN_KEY: 'licitafacil_token',
    USER_KEY: 'licitafacil_user',
    THEME_KEY: 'licitafacil_theme',

    // Supabase (carregado dinamicamente do backend)
    SUPABASE_URL: null,
    SUPABASE_ANON_KEY: null,
    SUPABASE_ENABLED: false,
    PASSWORD_POLICY: {
        min_length: 8,
        require_uppercase: true,
        require_lowercase: true,
        require_digit: true,
        require_special: true,
    },

    // Constantes de tempo (ms) centralizadas
    TIMEOUTS: {
        TOAST_DURATION: 5000,
        REDIRECT_DELAY: 1000,
        CLEANUP_INTERVAL: 30000,
        POLLING_INTERVAL: 3000,
        RENDER_INTERVAL: 5000,
        DEBOUNCE_INPUT: 500,
        REALTIME_RECONNECT: 500,
        INIT_DELAY: 2000,
        COMPLETION_HIGHLIGHT: 8000,
        JOBS_REFRESH: 10000,
    }
};

// Instância global do Supabase (inicializada após carregar config)
let supabaseClient = null;

// Promise para garantir que loadAuthConfig execute apenas uma vez
let authConfigPromise = null;
let passwordPolicyPromise = null;

/**
 * Carrega configuração de autenticação do backend
 * Detecta automaticamente se Supabase está habilitado
 * IDEMPOTENTE: múltiplas chamadas retornam a mesma Promise
 */
async function loadAuthConfig() {
    // Se já está carregando ou carregou, retorna a Promise existente
    if (authConfigPromise) {
        return authConfigPromise;
    }

    authConfigPromise = (async () => {
        try {
            const config = await api.get('/auth/config');

            if (config.supabase_enabled) {
                CONFIG.SUPABASE_URL = config.supabase_url;
                CONFIG.SUPABASE_ANON_KEY = config.supabase_anon_key;
                CONFIG.SUPABASE_ENABLED = true;

                // Inicializar cliente Supabase apenas se ainda não existe
                if (!supabaseClient && typeof window.supabase !== 'undefined') {
                    supabaseClient = window.supabase.createClient(
                        CONFIG.SUPABASE_URL,
                        CONFIG.SUPABASE_ANON_KEY
                    );
                    console.log('[AUTH] Supabase client initialized');
                }
            }

            return config;
        } catch (error) {
            console.warn('[AUTH] Failed to load auth config:', error);
            return { mode: 'legacy', supabase_enabled: false };
        }
    })();

    return authConfigPromise;
}

/**
 * Carrega política de senha do backend para manter frontend alinhado.
 * IDEMPOTENTE: múltiplas chamadas retornam a mesma Promise.
 */
async function loadPasswordPolicy() {
    if (passwordPolicyPromise) {
        return passwordPolicyPromise;
    }

    passwordPolicyPromise = (async () => {
        try {
            const data = await api.get('/auth/password-requirements');
            if (data && data.policy) {
                CONFIG.PASSWORD_POLICY = {
                    ...CONFIG.PASSWORD_POLICY,
                    ...data.policy,
                };
            }
            return CONFIG.PASSWORD_POLICY;
        } catch (error) {
            console.warn('[AUTH] Failed to load password policy:', error);
            return CONFIG.PASSWORD_POLICY;
        }
    })();

    return passwordPolicyPromise;
}

/**
 * Retorna o cliente Supabase se disponível
 */
function getSupabaseClient() {
    return supabaseClient;
}

/**
 * Verifica se Supabase está habilitado e disponível
 */
function isSupabaseAvailable() {
    return CONFIG.SUPABASE_ENABLED && supabaseClient !== null;
}

/**
 * Limpa todos os dados de sessão (usado pelo error handler)
 * @returns {Promise<void>}
 */
async function clearSessionData() {
    // 1. Limpar sessão Supabase
    if (isSupabaseAvailable()) {
        try {
            await supabaseClient.auth.signOut({ scope: 'local' });
        } catch (error) {
            console.warn('[CONFIG] Error signing out:', error);
        }
    }

    // 2. Limpar tokens da aplicação
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    localStorage.removeItem(CONFIG.USER_KEY);

    // 3. Limpar chaves Supabase do localStorage
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.startsWith('sb-') || key.startsWith('supabase'))) {
            keysToRemove.push(key);
        }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));
}

// Funções auxiliares para requisições à API
const api = {
    /**
     * Faz uma requisicao a API
     * @param {string} endpoint - Endpoint da API (ex: '/auth/login')
     * @param {object} options - Opcoes do fetch
     * @returns {Promise<object>} - Resposta da API
     */
    async request(endpoint, options = {}) {
        // Verificar conectividade antes de tentar requisicao
        if (!navigator.onLine) {
            ui.showAlert('Sem conexao com a internet. Verifique sua conexao.', 'error');
            throw new Error('Sem conexao com a internet');
        }

        const url = CONFIG.API_URL + CONFIG.API_PREFIX + endpoint;

        // Obter token (Supabase ou legacy)
        let token = null;
        if (isSupabaseAvailable()) {
            const { data: { session } } = await supabaseClient.auth.getSession();
            token = session?.access_token;
        }
        if (!token) {
            token = localStorage.getItem(CONFIG.TOKEN_KEY);
        }

        const method = String(options.method || 'GET').toUpperCase();
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
            headers['X-Requested-With'] = 'XMLHttpRequest';
        }

        try {
            const response = await fetch(url, {
                ...options,
                method,
                headers
            });

            let data = null;
            try {
                data = await response.json();
            } catch (_) {
                data = null;
            }

            if (!response.ok) {
                if (response.status === 401) {
                    // Se estamos na página de login, mostrar erro real (senha incorreta, etc)
                    const isLoginPage = window.location.pathname.endsWith('index.html') ||
                                        window.location.pathname === '/' ||
                                        window.location.pathname === '';

                    if (isLoginPage && data && data.detail) {
                        // Erro de autenticação na página de login - mostrar mensagem real
                        throw new Error(data.detail);
                    }

                    // Sessão expirada em outra página - limpar e redirecionar
                    await clearSessionData();
                    if (!isLoginPage) {
                        window.location.href = 'index.html';
                        return; // Evita processamento adicional durante redirect
                    }
                    throw new Error('Sessao expirada. Faca login novamente.');
                }
                // Formatar mensagem de erro (pode ser string ou array de validacao do Pydantic)
                let message = `Erro na requisicao (${response.status})`;
                if (data && data.detail) {
                    if (Array.isArray(data.detail)) {
                        // Erro de validacao Pydantic - extrair mensagens
                        message = data.detail.map(err => err.msg || err.message || String(err)).join('; ');
                    } else {
                        message = data.detail;
                    }
                }
                throw new Error(message);
            }

            return data;
        } catch (error) {
            console.error('Erro na API:', error);
            throw error;
        }
    },

    // Metodos convenientes
    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    post(endpoint, body) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    },

    put(endpoint, body) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    },

    delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },

    patch(endpoint, body) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(body)
        });
    },

    /**
     * Upload de arquivo
     * @param {string} endpoint - Endpoint da API
     * @param {FormData} formData - Dados do formulario com arquivo
     * @returns {Promise<object>} - Resposta da API
     */
    async upload(endpoint, formData) {
        const url = CONFIG.API_URL + CONFIG.API_PREFIX + endpoint;

        // Obter token (Supabase ou legacy)
        let token = null;
        if (isSupabaseAvailable()) {
            const { data: { session } } = await supabaseClient.auth.getSession();
            token = session?.access_token;
        }
        if (!token) {
            token = localStorage.getItem(CONFIG.TOKEN_KEY);
        }

        const headers = {
            'X-Requested-With': 'XMLHttpRequest',
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers,
                body: formData
            });

            let data = null;
            try {
                data = await response.json();
            } catch (_) {
                data = null;
            }

            if (!response.ok) {
                if (response.status === 401) {
                    // Sessão expirada - limpar e redirecionar para login
                    await clearSessionData();
                    if (!window.location.pathname.endsWith('index.html')) {
                        window.location.href = 'index.html';
                        return; // Evita processamento adicional durante redirect
                    }
                    throw new Error('Sessao expirada. Faca login novamente.');
                }
                // Formatar mensagem de erro (pode ser string ou array de validacao do Pydantic)
                let message = `Erro no upload (${response.status})`;
                if (data && data.detail) {
                    if (Array.isArray(data.detail)) {
                        message = data.detail.map(err => err.msg || err.message || String(err)).join('; ');
                    } else {
                        message = data.detail;
                    }
                }
                throw new Error(message);
            }

            return data;
        } catch (error) {
            console.error('Erro no upload:', error);
            throw error;
        }
    }
};

// Funções auxiliares de UI
const ui = {
    /**
     * Exibe um alerta na página
     * @param {string} message - Mensagem do alerta
     * @param {string} type - Tipo: success, error, warning, info
     * @param {string} containerId - ID do container do alerta
     */
    showAlert(message, type = 'info', containerId = 'alertContainer') {
        const container = document.getElementById(containerId);
        if (!container) return;

        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.setAttribute('role', 'alert');

        // Usar textContent para prevenir XSS
        const span = document.createElement('span');
        span.textContent = message;
        alert.appendChild(span);

        const button = document.createElement('button');
        button.textContent = '\u2715';
        button.style.cssText = 'background:none;border:none;cursor:pointer;margin-left:auto;';
        button.addEventListener('click', function() { this.parentElement.remove(); });
        alert.appendChild(button);

        container.appendChild(alert);

        // Remover automaticamente
        setTimeout(() => alert.remove(), CONFIG.TIMEOUTS.TOAST_DURATION);
    },

    /**
     * Mostra/esconde loading em um botão
     * @param {HTMLButtonElement} button - Botão
     * @param {boolean} loading - Se está carregando
     * @param {string} textId - ID do span de texto
     * @param {string} spinnerId - ID do spinner
     */
    setButtonLoading(button, loading, textId, spinnerId) {
        const text = document.getElementById(textId);
        const spinner = document.getElementById(spinnerId);

        if (loading) {
            button.disabled = true;
            text?.classList.add('hidden');
            spinner?.classList.remove('hidden');
        } else {
            button.disabled = false;
            text?.classList.remove('hidden');
            spinner?.classList.add('hidden');
        }
    }
};

// Gerenciamento de tema
const theme = {
    init() {
        const savedTheme = localStorage.getItem(CONFIG.THEME_KEY) || 'light';
        this.set(savedTheme);
    },

    get() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    },

    set(themeName) {
        document.documentElement.setAttribute('data-theme', themeName);
        localStorage.setItem(CONFIG.THEME_KEY, themeName);
    },

    toggle() {
        const current = this.get();
        const next = current === 'light' ? 'dark' : 'light';
        this.set(next);
        return next;
    }
};

// Inicializar tema
theme.init();

/**
 * Cria uma versao debounced de uma funcao
 * @param {Function} fn - Funcao a debounce
 * @param {number} delay - Delay em ms (default: CONFIG.TIMEOUTS.DEBOUNCE_INPUT)
 * @returns {Function} Funcao debounced
 */
ui.debounce = function(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay || CONFIG.TIMEOUTS.DEBOUNCE_INPUT);
    };
};

// Deteccao de conectividade
window.addEventListener('online', () => ui.showAlert('Conexao restaurada!', 'success'));
window.addEventListener('offline', () => ui.showAlert('Conexao perdida. Algumas funcionalidades podem nao funcionar.', 'warning'));
