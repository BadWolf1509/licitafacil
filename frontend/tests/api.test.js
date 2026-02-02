/**
 * Testes para o modulo api (definido em config.js)
 *
 * Testa todas as funcoes do objeto api: request, get, post, put, delete, patch, upload
 */

// Mock do objeto api (replica implementacao de config.js)
const createApi = () => ({
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
                    const isLoginPage = window.location.pathname.endsWith('index.html') ||
                                        window.location.pathname === '/' ||
                                        window.location.pathname === '';

                    if (isLoginPage && data && data.detail) {
                        throw new Error(data.detail);
                    }

                    localStorage.removeItem(CONFIG.TOKEN_KEY);
                    localStorage.removeItem(CONFIG.USER_KEY);
                    if (!isLoginPage) {
                        window.location.href = 'index.html';
                    }
                    throw new Error('Sessao expirada. Faca login novamente.');
                }

                let message = `Erro na requisicao (${response.status})`;
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
            throw error;
        }
    },

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

    async upload(endpoint, formData) {
        const url = CONFIG.API_URL + CONFIG.API_PREFIX + endpoint;
        const token = localStorage.getItem(CONFIG.TOKEN_KEY);

        const headers = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

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
                throw new Error('Sessao expirada. Faca login novamente.');
            }

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
    }
});

describe('api.request', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
        localStorage.clear();
    });

    test('deve construir URL corretamente', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({ ok: true }));

        await api.get('/usuarios');

        expect(fetch).toHaveBeenCalledWith(
            CONFIG.API_URL + CONFIG.API_PREFIX + '/usuarios',
            expect.any(Object)
        );
    });

    test('deve adicionar Content-Type application/json', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({ ok: true }));

        await api.get('/test');

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                headers: expect.objectContaining({
                    'Content-Type': 'application/json'
                })
            })
        );
    });

    test('deve adicionar Authorization quando token existe', async () => {
        localStorage.setItem(CONFIG.TOKEN_KEY, 'meu_token_jwt');
        fetch.mockImplementationOnce(() => mockFetchResponse({ ok: true }));

        await api.get('/test');

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                headers: expect.objectContaining({
                    'Authorization': 'Bearer meu_token_jwt'
                })
            })
        );
    });

    test('nao deve adicionar Authorization quando token nao existe', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({ ok: true }));

        await api.get('/test');

        const callHeaders = fetch.mock.calls[0][1].headers;
        expect(callHeaders['Authorization']).toBeUndefined();
    });

    test('deve retornar dados da resposta JSON', async () => {
        const expectedData = { id: 1, nome: 'Teste' };
        fetch.mockImplementationOnce(() => mockFetchResponse(expectedData));

        const result = await api.get('/test');

        expect(result).toEqual(expectedData);
    });
});

describe('api.get', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
    });

    test('deve fazer requisicao com metodo GET', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({}));

        await api.get('/usuarios');

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({ method: 'GET' })
        );
    });
});

describe('api.post', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
    });

    test('deve fazer requisicao com metodo POST', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({}));

        await api.post('/usuarios', { nome: 'Teste' });

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({ method: 'POST' })
        );
    });

    test('deve enviar body como JSON', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({}));

        const body = { nome: 'Teste', email: 'teste@example.com' };
        await api.post('/usuarios', body);

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                body: JSON.stringify(body)
            })
        );
    });
});

describe('api.put', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
    });

    test('deve fazer requisicao com metodo PUT', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({}));

        await api.put('/usuarios/1', { nome: 'Atualizado' });

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({ method: 'PUT' })
        );
    });

    test('deve enviar body como JSON', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({}));

        const body = { nome: 'Atualizado' };
        await api.put('/usuarios/1', body);

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                body: JSON.stringify(body)
            })
        );
    });
});

describe('api.delete', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
    });

    test('deve fazer requisicao com metodo DELETE', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({}));

        await api.delete('/usuarios/1');

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({ method: 'DELETE' })
        );
    });
});

describe('api.patch', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
    });

    test('deve fazer requisicao com metodo PATCH', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({}));

        await api.patch('/usuarios/1', { status: 'ativo' });

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({ method: 'PATCH' })
        );
    });

    test('deve enviar body como JSON', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({}));

        const body = { status: 'ativo' };
        await api.patch('/usuarios/1', body);

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                body: JSON.stringify(body)
            })
        );
    });
});

describe('api.upload', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
        localStorage.clear();
    });

    test('deve fazer requisicao POST com FormData', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({ success: true }));

        const formData = new FormData();
        formData.append('file', new Blob(['test']), 'test.pdf');

        await api.upload('/atestados', formData);

        expect(fetch).toHaveBeenCalledWith(
            expect.stringContaining('/atestados'),
            expect.objectContaining({
                method: 'POST',
                body: formData
            })
        );
    });

    test('nao deve adicionar Content-Type para FormData', async () => {
        fetch.mockImplementationOnce(() => mockFetchResponse({ success: true }));

        const formData = new FormData();
        await api.upload('/atestados', formData);

        const callHeaders = fetch.mock.calls[0][1].headers;
        expect(callHeaders['Content-Type']).toBeUndefined();
    });

    test('deve adicionar Authorization quando token existe', async () => {
        localStorage.setItem(CONFIG.TOKEN_KEY, 'meu_token');
        fetch.mockImplementationOnce(() => mockFetchResponse({ success: true }));

        const formData = new FormData();
        await api.upload('/atestados', formData);

        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                headers: expect.objectContaining({
                    'Authorization': 'Bearer meu_token'
                })
            })
        );
    });
});

describe('Tratamento de erros', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
        localStorage.clear();
        // Simular pagina dashboard
        Object.defineProperty(window, 'location', {
            value: { pathname: '/dashboard.html', href: '' },
            writable: true,
        });
    });

    test('deve lancar erro com mensagem do backend', async () => {
        fetch.mockImplementationOnce(() => mockFetchError('Email ja cadastrado', 400));

        await expect(api.post('/auth/registrar', {})).rejects.toThrow('Email ja cadastrado');
    });

    test('deve lancar erro generico quando nao ha detail', async () => {
        fetch.mockImplementationOnce(() =>
            Promise.resolve({
                ok: false,
                status: 500,
                json: () => Promise.resolve({})
            })
        );

        await expect(api.get('/test')).rejects.toThrow('Erro na requisicao (500)');
    });

    test('deve formatar erros de validacao Pydantic', async () => {
        fetch.mockImplementationOnce(() =>
            Promise.resolve({
                ok: false,
                status: 422,
                json: () => Promise.resolve({
                    detail: [
                        { msg: 'Campo obrigatorio' },
                        { msg: 'Email invalido' }
                    ]
                })
            })
        );

        await expect(api.post('/test', {})).rejects.toThrow('Campo obrigatorio; Email invalido');
    });

    test('deve limpar localStorage em erro 401 fora da pagina login', async () => {
        localStorage.setItem(CONFIG.TOKEN_KEY, 'token_antigo');
        localStorage.setItem(CONFIG.USER_KEY, 'user_data');

        fetch.mockImplementationOnce(() => mockFetchError('Token invalido', 401));

        await expect(api.get('/test')).rejects.toThrow();

        expect(localStorage.getItem(CONFIG.TOKEN_KEY)).toBeNull();
        expect(localStorage.getItem(CONFIG.USER_KEY)).toBeNull();
    });

    test('deve mostrar mensagem real de erro 401 na pagina de login', async () => {
        Object.defineProperty(window, 'location', {
            value: { pathname: '/index.html', href: '' },
            writable: true,
        });

        fetch.mockImplementationOnce(() => mockFetchError('Senha incorreta', 401));

        await expect(api.post('/auth/login', {})).rejects.toThrow('Senha incorreta');
    });
});

describe('Erros de rede', () => {
    let api;

    beforeEach(() => {
        api = createApi();
        fetch.mockClear();
    });

    test('deve propagar erro de rede', async () => {
        fetch.mockImplementationOnce(() => Promise.reject(new Error('Network error')));

        await expect(api.get('/test')).rejects.toThrow('Network error');
    });

    test('deve propagar erro de timeout', async () => {
        fetch.mockImplementationOnce(() => Promise.reject(new Error('Timeout')));

        await expect(api.get('/test')).rejects.toThrow('Timeout');
    });
});
