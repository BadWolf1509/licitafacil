// LicitaFácil - Autenticação

document.addEventListener('DOMContentLoaded', () => {
    // Só executar configuração de login na página de login (index.html)
    const path = window.location.pathname.toLowerCase();
    const isLoginPage = path.endsWith('index.html') ||
                        path.endsWith('/frontend/') ||
                        path === '/' ||
                        (!path.includes('.html') && path.endsWith('/'));

    if (isLoginPage && document.getElementById('loginForm')) {
        // Verificar se já está logado
        checkAuth();

        // Configurar tabs
        setupTabs();

        // Configurar formulários
        setupLoginForm();
        setupRegistroForm();
    }
});

/**
 * Verifica se o usuário já está autenticado
 */
function checkAuth() {
    const token = localStorage.getItem(CONFIG.TOKEN_KEY);
    if (token) {
        // Verificar se o token é válido
        api.get('/auth/status')
            .then(data => {
                // Token válido, redirecionar para dashboard
                if (data.aprovado) {
                    window.location.href = 'dashboard.html';
                } else {
                    // Usuário não aprovado
                    ui.showAlert('Seu cadastro está aguardando aprovação do administrador.', 'warning');
                    localStorage.removeItem(CONFIG.TOKEN_KEY);
                }
            })
            .catch(() => {
                // Token inválido, limpar
                localStorage.removeItem(CONFIG.TOKEN_KEY);
            });
    }
}

/**
 * Configura as tabs de login/registro
 */
function setupTabs() {
    const tabs = document.querySelectorAll('.auth-tab');
    const forms = document.querySelectorAll('.auth-form');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;

            // Atualizar tabs ativas
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Atualizar formulários ativos
            forms.forEach(form => {
                form.classList.remove('active');
                if (form.id === `${targetTab}Form`) {
                    form.classList.add('active');
                }
            });

            // Limpar alertas
            document.getElementById('alertContainer').innerHTML = '';
        });
    });
}

/**
 * Valida formato de email
 * @param {string} email - Email a validar
 * @returns {boolean} - true se válido
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Valida complexidade da senha
 * @param {string} password - Senha a validar
 * @returns {{valid: boolean, errors: string[]}} - Resultado da validação
 */
function validatePassword(password) {
    const errors = [];
    const minLength = 8;

    if (!password || password.length < minLength) {
        errors.push(`Mínimo ${minLength} caracteres`);
    }
    if (!/[A-Z]/.test(password)) {
        errors.push('Pelo menos 1 letra maiúscula');
    }
    if (!/[a-z]/.test(password)) {
        errors.push('Pelo menos 1 letra minúscula');
    }
    if (!/[0-9]/.test(password)) {
        errors.push('Pelo menos 1 número');
    }

    return {
        valid: errors.length === 0,
        errors: errors
    };
}

/**
 * Formata erros de senha para exibição
 * @param {string[]} errors - Lista de erros
 * @returns {string} - Mensagem formatada
 */
function formatPasswordErrors(errors) {
    if (errors.length === 1) {
        return errors[0];
    }
    return errors.join(', ');
}

/**
 * Mostra erro de validação em um input
 * @param {HTMLElement} input - Input element
 * @param {string} message - Mensagem de erro
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
 * Limpa erro de validação de um input
 * @param {HTMLElement} input - Input element
 */
function clearInputError(input) {
    input.classList.remove('input-error');
    const errorEl = input.parentElement.querySelector('.input-error-message');
    if (errorEl) {
        errorEl.remove();
    }
}

/**
 * Configura o formulário de login
 */
function setupLoginForm() {
    const form = document.getElementById('loginForm');
    const button = form.querySelector('button[type="submit"]');
    const emailInput = document.getElementById('loginEmail');

    // Validação em tempo real do email
    emailInput.addEventListener('blur', () => {
        if (emailInput.value && !isValidEmail(emailInput.value)) {
            showInputError(emailInput, 'Email inválido');
        } else {
            clearInputError(emailInput);
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const email = document.getElementById('loginEmail').value;
        const senha = document.getElementById('loginSenha').value;

        // Validação de email
        if (!isValidEmail(email)) {
            showInputError(emailInput, 'Email inválido');
            ui.showAlert('Por favor, insira um email válido', 'error');
            return;
        }

        ui.setButtonLoading(button, true, 'loginBtnText', 'loginSpinner');

        try {
            const data = await api.post('/auth/login-json', { email, senha });

            // Salvar token
            localStorage.setItem(CONFIG.TOKEN_KEY, data.access_token);

            // Verificar status do usuário
            const status = await api.get('/auth/status');

            if (status.aprovado) {
                ui.showAlert('Login realizado com sucesso!', 'success');
                setTimeout(() => {
                    window.location.href = 'dashboard.html';
                }, 1000);
            } else {
                ui.showAlert('Seu cadastro está aguardando aprovação do administrador.', 'warning');
                localStorage.removeItem(CONFIG.TOKEN_KEY);
            }
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao fazer login', 'error');
        } finally {
            ui.setButtonLoading(button, false, 'loginBtnText', 'loginSpinner');
        }
    });
}

/**
 * Configura o formulário de registro
 */
function setupRegistroForm() {
    const form = document.getElementById('registroForm');
    const button = form.querySelector('button[type="submit"]');
    const emailInput = document.getElementById('registroEmail');
    const senhaInput = document.getElementById('registroSenha');
    const confirmarSenhaInput = document.getElementById('registroConfirmarSenha');

    // Validação em tempo real do email
    emailInput.addEventListener('blur', () => {
        if (emailInput.value && !isValidEmail(emailInput.value)) {
            showInputError(emailInput, 'Email inválido');
        } else {
            clearInputError(emailInput);
        }
    });

    // Validação em tempo real da senha
    senhaInput.addEventListener('blur', () => {
        if (senhaInput.value) {
            const validation = validatePassword(senhaInput.value);
            if (!validation.valid) {
                showInputError(senhaInput, formatPasswordErrors(validation.errors));
            } else {
                clearInputError(senhaInput);
            }
        } else {
            clearInputError(senhaInput);
        }
    });

    // Validação em tempo real da confirmação de senha
    confirmarSenhaInput.addEventListener('blur', () => {
        if (confirmarSenhaInput.value && confirmarSenhaInput.value !== senhaInput.value) {
            showInputError(confirmarSenhaInput, 'Senhas não coincidem');
        } else {
            clearInputError(confirmarSenhaInput);
        }
    });

    // Validar confirmação quando senha muda
    senhaInput.addEventListener('input', () => {
        if (confirmarSenhaInput.value) {
            if (confirmarSenhaInput.value !== senhaInput.value) {
                showInputError(confirmarSenhaInput, 'Senhas não coincidem');
            } else {
                clearInputError(confirmarSenhaInput);
            }
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const nome = document.getElementById('registroNome').value;
        const email = document.getElementById('registroEmail').value;
        const senha = document.getElementById('registroSenha').value;
        const confirmarSenha = document.getElementById('registroConfirmarSenha').value;

        // Validação de email
        if (!isValidEmail(email)) {
            showInputError(emailInput, 'Email inválido');
            ui.showAlert('Por favor, insira um email válido', 'error');
            return;
        }

        // Validações de senha
        const passwordValidation = validatePassword(senha);
        if (!passwordValidation.valid) {
            showInputError(senhaInput, formatPasswordErrors(passwordValidation.errors));
            ui.showAlert('Senha inválida: ' + formatPasswordErrors(passwordValidation.errors), 'error');
            return;
        }

        if (senha !== confirmarSenha) {
            showInputError(confirmarSenhaInput, 'Senhas não coincidem');
            ui.showAlert('As senhas não coincidem', 'error');
            return;
        }

        ui.setButtonLoading(button, true, 'registroBtnText', 'registroSpinner');

        try {
            const data = await api.post('/auth/registrar', { nome, email, senha });

            ui.showAlert(data.mensagem || 'Cadastro realizado com sucesso!', 'success');

            // Limpar formulário
            form.reset();

            // Mudar para aba de login
            document.querySelector('[data-tab="login"]').click();

        } catch (error) {
            ui.showAlert(error.message || 'Erro ao realizar cadastro', 'error');
        } finally {
            ui.setButtonLoading(button, false, 'registroBtnText', 'registroSpinner');
        }
    });
}

/**
 * Faz logout do usuário
 */
function logout() {
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    localStorage.removeItem(CONFIG.USER_KEY);
    window.location.href = 'index.html';
}

/**
 * Alterna a visibilidade da senha
 * @param {string} inputId - ID do input de senha
 * @param {HTMLElement} button - Botão que foi clicado
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
