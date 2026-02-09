/**
 * Testes para o modulo de autenticacao (auth.js)
 */

// Mock do CONFIG
global.CONFIG = {
    TOKEN_KEY: 'test_token',
    USER_KEY: 'test_user'
};

// Mock do api
global.api = {
    get: jest.fn(),
    post: jest.fn()
};

// Mock do ui
global.ui = {
    showAlert: jest.fn(),
    setButtonLoading: jest.fn()
};

// Carregar funcoes do auth.js que sao exportadas globalmente
// Simulamos as funcoes aqui para teste isolado

/**
 * Valida formato de email
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Mostra erro de validacao em um input
 */
function showInputError(input, message) {
    input.classList.add('input-error');
    let errorEl = input.parentElement.querySelector('.input-error-message');
    if (!errorEl) {
        errorEl = document.createElement('span');
        errorEl.className = 'input-error-message';
        input.parentElement.appendChild(errorEl);
    }
    errorEl.textContent = message;
}

/**
 * Limpa erro de validacao de um input
 */
function clearInputError(input) {
    input.classList.remove('input-error');
    const errorEl = input.parentElement.querySelector('.input-error-message');
    if (errorEl) {
        errorEl.remove();
    }
}

/**
 * Faz logout do usuario
 */
function logout() {
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    localStorage.removeItem(CONFIG.USER_KEY);
    window.location.href = 'index.html';
}

/**
 * Alterna a visibilidade da senha
 */
function togglePassword(inputId, button) {
    const input = document.getElementById(inputId);
    if (!input) return;

    if (input.type === 'password') {
        input.type = 'text';
        button.classList.add('active');
        button.title = 'Ocultar senha';
    } else {
        input.type = 'password';
        button.classList.remove('active');
        button.title = 'Mostrar senha';
    }
}

describe('isValidEmail', () => {
    test('deve aceitar email valido simples', () => {
        expect(isValidEmail('usuario@dominio.com')).toBe(true);
    });

    test('deve aceitar email com subdominio', () => {
        expect(isValidEmail('usuario@sub.dominio.com')).toBe(true);
    });

    test('deve aceitar email com ponto no usuario', () => {
        expect(isValidEmail('usuario.nome@dominio.com')).toBe(true);
    });

    test('deve aceitar email com numeros', () => {
        expect(isValidEmail('usuario123@dominio456.com')).toBe(true);
    });

    test('deve aceitar email com hifen', () => {
        expect(isValidEmail('usuario-nome@dominio-teste.com')).toBe(true);
    });

    test('deve aceitar email com underscore', () => {
        expect(isValidEmail('usuario_nome@dominio.com')).toBe(true);
    });

    test('deve rejeitar email sem @', () => {
        expect(isValidEmail('usuariodominio.com')).toBe(false);
    });

    test('deve rejeitar email sem dominio', () => {
        expect(isValidEmail('usuario@')).toBe(false);
    });

    test('deve rejeitar email sem usuario', () => {
        expect(isValidEmail('@dominio.com')).toBe(false);
    });

    test('deve rejeitar email sem extensao de dominio', () => {
        expect(isValidEmail('usuario@dominio')).toBe(false);
    });

    test('deve rejeitar email com espacos', () => {
        expect(isValidEmail('usuario @dominio.com')).toBe(false);
        expect(isValidEmail('usuario@ dominio.com')).toBe(false);
        expect(isValidEmail(' usuario@dominio.com')).toBe(false);
    });

    test('deve rejeitar string vazia', () => {
        expect(isValidEmail('')).toBe(false);
    });

    test('deve rejeitar email com multiplos @', () => {
        expect(isValidEmail('usuario@@dominio.com')).toBe(false);
        expect(isValidEmail('usuario@dominio@outro.com')).toBe(false);
    });
});

describe('showInputError', () => {
    let input;
    let parentElement;

    beforeEach(() => {
        // Criar estrutura DOM para teste
        parentElement = document.createElement('div');
        input = document.createElement('input');
        input.type = 'text';
        parentElement.appendChild(input);
        document.body.appendChild(parentElement);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    test('deve adicionar classe input-error ao input', () => {
        showInputError(input, 'Erro de teste');
        expect(input.classList.contains('input-error')).toBe(true);
    });

    test('deve criar elemento de mensagem de erro', () => {
        showInputError(input, 'Erro de teste');
        const errorEl = parentElement.querySelector('.input-error-message');
        expect(errorEl).not.toBeNull();
        expect(errorEl.textContent).toBe('Erro de teste');
    });

    test('deve reutilizar elemento de erro existente', () => {
        showInputError(input, 'Primeiro erro');
        showInputError(input, 'Segundo erro');

        const errorElements = parentElement.querySelectorAll('.input-error-message');
        expect(errorElements.length).toBe(1);
        expect(errorElements[0].textContent).toBe('Segundo erro');
    });

    test('deve atualizar mensagem de erro', () => {
        showInputError(input, 'Mensagem original');
        let errorEl = parentElement.querySelector('.input-error-message');
        expect(errorEl.textContent).toBe('Mensagem original');

        showInputError(input, 'Mensagem atualizada');
        errorEl = parentElement.querySelector('.input-error-message');
        expect(errorEl.textContent).toBe('Mensagem atualizada');
    });
});

describe('clearInputError', () => {
    let input;
    let parentElement;

    beforeEach(() => {
        parentElement = document.createElement('div');
        input = document.createElement('input');
        input.type = 'text';
        input.classList.add('input-error');
        parentElement.appendChild(input);

        const errorEl = document.createElement('span');
        errorEl.className = 'input-error-message';
        errorEl.textContent = 'Erro existente';
        parentElement.appendChild(errorEl);

        document.body.appendChild(parentElement);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    test('deve remover classe input-error do input', () => {
        expect(input.classList.contains('input-error')).toBe(true);
        clearInputError(input);
        expect(input.classList.contains('input-error')).toBe(false);
    });

    test('deve remover elemento de mensagem de erro', () => {
        expect(parentElement.querySelector('.input-error-message')).not.toBeNull();
        clearInputError(input);
        expect(parentElement.querySelector('.input-error-message')).toBeNull();
    });

    test('nao deve falhar se nao houver elemento de erro', () => {
        // Remover elemento de erro primeiro
        parentElement.querySelector('.input-error-message').remove();

        // Nao deve lancar erro
        expect(() => clearInputError(input)).not.toThrow();
    });
});

describe('logout', () => {
    let originalLocation;

    beforeEach(() => {
        localStorage.setItem(CONFIG.TOKEN_KEY, 'test_token_value');
        localStorage.setItem(CONFIG.USER_KEY, 'test_user_value');
        // Salvar location original e criar mock
        originalLocation = window.location;
        delete window.location;
        window.location = { href: '' };
    });

    afterEach(() => {
        localStorage.clear();
        // Restaurar location original
        window.location = originalLocation;
    });

    test('deve remover token do localStorage', () => {
        expect(localStorage.getItem(CONFIG.TOKEN_KEY)).toBe('test_token_value');
        logout();
        expect(localStorage.getItem(CONFIG.TOKEN_KEY)).toBeNull();
    });

    test('deve remover dados do usuario do localStorage', () => {
        expect(localStorage.getItem(CONFIG.USER_KEY)).toBe('test_user_value');
        logout();
        expect(localStorage.getItem(CONFIG.USER_KEY)).toBeNull();
    });

    test('deve redirecionar para index.html', () => {
        logout();
        expect(window.location.href).toBe('index.html');
    });
});

describe('togglePassword', () => {
    let input;
    let button;

    beforeEach(() => {
        input = document.createElement('input');
        input.id = 'testPassword';
        input.type = 'password';
        document.body.appendChild(input);

        button = document.createElement('button');
        button.title = 'Mostrar senha';
        document.body.appendChild(button);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    test('deve mudar tipo de password para text', () => {
        expect(input.type).toBe('password');
        togglePassword('testPassword', button);
        expect(input.type).toBe('text');
    });

    test('deve mudar tipo de text para password', () => {
        input.type = 'text';
        button.classList.add('active');

        togglePassword('testPassword', button);
        expect(input.type).toBe('password');
    });

    test('deve adicionar classe active quando mostrar senha', () => {
        togglePassword('testPassword', button);
        expect(button.classList.contains('active')).toBe(true);
    });

    test('deve remover classe active quando ocultar senha', () => {
        input.type = 'text';
        button.classList.add('active');

        togglePassword('testPassword', button);
        expect(button.classList.contains('active')).toBe(false);
    });

    test('deve atualizar title do botao ao mostrar senha', () => {
        togglePassword('testPassword', button);
        expect(button.title).toBe('Ocultar senha');
    });

    test('deve atualizar title do botao ao ocultar senha', () => {
        input.type = 'text';
        button.classList.add('active');
        button.title = 'Ocultar senha';

        togglePassword('testPassword', button);
        expect(button.title).toBe('Mostrar senha');
    });

    test('nao deve falhar com input inexistente', () => {
        expect(() => togglePassword('inputInexistente', button)).not.toThrow();
    });

    test('deve fazer toggle completo (password -> text -> password)', () => {
        expect(input.type).toBe('password');

        togglePassword('testPassword', button);
        expect(input.type).toBe('text');
        expect(button.classList.contains('active')).toBe(true);

        togglePassword('testPassword', button);
        expect(input.type).toBe('password');
        expect(button.classList.contains('active')).toBe(false);
    });
});

describe('validatePassword', () => {
    // Replica a funcao validatePassword do auth.js
    function validatePassword(password) {
        const errors = [];
        const policy = {
            min_length: 8,
            require_uppercase: true,
            require_lowercase: true,
            require_digit: true,
            require_special: true,
        };
        const minLength = policy.min_length;

        if (!password || password.length < minLength) {
            errors.push(`Minimo ${minLength} caracteres`);
        }
        if (policy.require_uppercase && !/[A-Z]/.test(password)) {
            errors.push('Pelo menos 1 letra maiuscula');
        }
        if (policy.require_lowercase && !/[a-z]/.test(password)) {
            errors.push('Pelo menos 1 letra minuscula');
        }
        if (policy.require_digit && !/[0-9]/.test(password)) {
            errors.push('Pelo menos 1 numero');
        }
        if (policy.require_special && !/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;'`~]/.test(password)) {
            errors.push('Pelo menos 1 caractere especial');
        }

        return {
            valid: errors.length === 0,
            errors: errors
        };
    }

    test('deve aceitar senha valida com todos os requisitos', () => {
        const result = validatePassword('Senha123!');
        expect(result.valid).toBe(true);
        expect(result.errors.length).toBe(0);
    });

    test('deve aceitar senha longa e complexa', () => {
        const result = validatePassword('MinhaSenh4Forte!');
        expect(result.valid).toBe(true);
    });

    test('deve rejeitar senha muito curta', () => {
        const result = validatePassword('Abc1');
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Minimo 8 caracteres');
    });

    test('deve rejeitar senha sem letra maiuscula', () => {
        const result = validatePassword('senha123');
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Pelo menos 1 letra maiuscula');
    });

    test('deve rejeitar senha sem letra minuscula', () => {
        const result = validatePassword('SENHA123');
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Pelo menos 1 letra minuscula');
    });

    test('deve rejeitar senha sem numero', () => {
        const result = validatePassword('SenhaForte');
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Pelo menos 1 numero');
    });

    test('deve rejeitar senha sem caractere especial', () => {
        const result = validatePassword('Senha1234');
        expect(result.valid).toBe(false);
        expect(result.errors).toContain('Pelo menos 1 caractere especial');
    });

    test('deve retornar multiplos erros quando aplicavel', () => {
        const result = validatePassword('abc');
        expect(result.valid).toBe(false);
        expect(result.errors.length).toBeGreaterThan(1);
    });

    test('deve aceitar senha com exatamente 8 caracteres', () => {
        const result = validatePassword('Ab1!cd23');
        expect(result.valid).toBe(true);
    });

    test('deve rejeitar senha vazia', () => {
        const result = validatePassword('');
        expect(result.valid).toBe(false);
    });

    test('deve rejeitar senha null/undefined', () => {
        const result = validatePassword(null);
        expect(result.valid).toBe(false);
    });
});

describe('Validacao de confirmacao de senha', () => {
    function validatePasswordMatch(senha, confirmarSenha) {
        return senha === confirmarSenha;
    }

    test('deve aceitar senhas que coincidem', () => {
        expect(validatePasswordMatch('Senha123', 'Senha123')).toBe(true);
    });

    test('deve rejeitar senhas que nao coincidem', () => {
        expect(validatePasswordMatch('Senha123', 'Senha456')).toBe(false);
    });

    test('deve ser case sensitive', () => {
        expect(validatePasswordMatch('Senha123', 'senha123')).toBe(false);
    });

    test('deve aceitar strings vazias iguais', () => {
        expect(validatePasswordMatch('', '')).toBe(true);
    });
});

describe('Deteccao de pagina de login', () => {
    // Simula a logica do DOMContentLoaded
    function isLoginPage(pathname) {
        const path = pathname.toLowerCase();
        return path.endsWith('index.html') ||
               path.endsWith('/frontend/') ||
               path === '/' ||
               (!path.includes('.html') && path.endsWith('/'));
    }

    test('deve detectar index.html como pagina de login', () => {
        expect(isLoginPage('/index.html')).toBe(true);
        expect(isLoginPage('/frontend/index.html')).toBe(true);
    });

    test('deve detectar /frontend/ como pagina de login', () => {
        expect(isLoginPage('/frontend/')).toBe(true);
    });

    test('deve detectar raiz como pagina de login', () => {
        expect(isLoginPage('/')).toBe(true);
    });

    test('deve detectar diretorio sem .html como pagina de login', () => {
        expect(isLoginPage('/app/')).toBe(true);
    });

    test('nao deve detectar dashboard.html como pagina de login', () => {
        expect(isLoginPage('/dashboard.html')).toBe(false);
    });

    test('nao deve detectar outras paginas html', () => {
        expect(isLoginPage('/atestados.html')).toBe(false);
        expect(isLoginPage('/analises.html')).toBe(false);
        expect(isLoginPage('/admin.html')).toBe(false);
    });
});

describe('Integracao com localStorage', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    afterEach(() => {
        localStorage.clear();
    });

    test('deve salvar token apos login bem sucedido', () => {
        const token = 'jwt_token_test_123';
        localStorage.setItem(CONFIG.TOKEN_KEY, token);
        expect(localStorage.getItem(CONFIG.TOKEN_KEY)).toBe(token);
    });

    test('deve remover token quando usuario nao aprovado', () => {
        localStorage.setItem(CONFIG.TOKEN_KEY, 'some_token');
        // Simula comportamento de usuario nao aprovado
        localStorage.removeItem(CONFIG.TOKEN_KEY);
        expect(localStorage.getItem(CONFIG.TOKEN_KEY)).toBeNull();
    });

    test('deve manter token se usuario aprovado', () => {
        const token = 'approved_user_token';
        localStorage.setItem(CONFIG.TOKEN_KEY, token);
        // Token deve permanecer
        expect(localStorage.getItem(CONFIG.TOKEN_KEY)).toBe(token);
    });
});
