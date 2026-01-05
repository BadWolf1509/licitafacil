// Configurações globais do LicitaFácil

const CONFIG = {
    // URL base da API (alterar em produção)
    API_URL: window.location.origin,

    // Chaves do localStorage
    TOKEN_KEY: 'licitafacil_token',
    USER_KEY: 'licitafacil_user',
    THEME_KEY: 'licitafacil_theme'
};

// Funções auxiliares para requisições à API
const api = {
    /**
     * Faz uma requisição à API
     * @param {string} endpoint - Endpoint da API (ex: '/auth/login')
     * @param {object} options - Opções do fetch
     * @returns {Promise<object>} - Resposta da API
     */
    async request(endpoint, options = {}) {
        const url = CONFIG.API_URL + endpoint;
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

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Erro na requisição');
            }

            return data;
        } catch (error) {
            console.error('Erro na API:', error);
            throw error;
        }
    },

    // Métodos convenientes
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
     * @param {FormData} formData - Dados do formulário com arquivo
     * @returns {Promise<object>} - Resposta da API
     */
    async upload(endpoint, formData) {
        const url = CONFIG.API_URL + endpoint;
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

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Erro no upload');
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
