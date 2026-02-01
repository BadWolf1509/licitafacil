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
    THEME_KEY: 'licitafacil_theme'
};

// Funções auxiliares para requisições à API
const api = {
    /**
     * Faz uma requisicao a API
     * @param {string} endpoint - Endpoint da API (ex: '/auth/login')
     * @param {object} options - Opcoes do fetch
     * @returns {Promise<object>} - Resposta da API
     */
    async request(endpoint, options = {}) {
        const url = CONFIG.API_URL + CONFIG.API_PREFIX + endpoint;
        const token = localStorage.getItem(CONFIG.TOKEN_KEY);

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
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
                    localStorage.removeItem(CONFIG.TOKEN_KEY);
                    localStorage.removeItem(CONFIG.USER_KEY);
                    if (!window.location.pathname.endsWith('index.html')) {
                        window.location.href = 'index.html';
                    }
                    throw new Error('Sessao expirada. Faca login novamente.');
                }
                const message = (data && data.detail) ? data.detail : `Erro na requisicao (${response.status})`;
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
        const token = localStorage.getItem(CONFIG.TOKEN_KEY);

        const headers = {};
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
                    localStorage.removeItem(CONFIG.TOKEN_KEY);
                    localStorage.removeItem(CONFIG.USER_KEY);
                    if (!window.location.pathname.endsWith('index.html')) {
                        window.location.href = 'index.html';
                    }
                    throw new Error('Sessao expirada. Faca login novamente.');
                }
                const message = (data && data.detail) ? data.detail : `Erro no upload (${response.status})`;
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
        alert.innerHTML = `
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" style="background:none;border:none;cursor:pointer;margin-left:auto;">✕</button>
        `;
        container.appendChild(alert);

        // Remover automaticamente após 5 segundos
        setTimeout(() => alert.remove(), 5000);
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
