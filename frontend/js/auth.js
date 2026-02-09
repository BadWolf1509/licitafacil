// LicitaFácil - Autenticação
// Autenticação via Supabase Auth

document.addEventListener('DOMContentLoaded', async () => {
    // Carregar configuração de autenticação do backend em TODAS as páginas
    // Necessário para inicializar o cliente Supabase (usado pelo Realtime)
    await loadAuthConfig();
    await loadPasswordPolicy();

    // Só executar configuração de login na página de login (index.html)
    const path = window.location.pathname.toLowerCase();
    const isLoginPage = path.endsWith('index.html') ||
                        path.endsWith('/frontend/') ||
                        path === '/' ||
                        (!path.includes('.html') && path.endsWith('/'));

    if (isLoginPage && document.getElementById('loginForm')) {
        // Configurar password toggles via event delegation
        setupPasswordToggles();

        // Verificar se já está logado
        await checkAuth();

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
async function checkAuth() {
    let hasValidSession = false;

    // Verificar sessão Supabase
    if (isSupabaseAvailable()) {
        try {
            const { data: { session } } = await getSupabaseClient().auth.getSession();
            if (session) {
                hasValidSession = true;
            }
        } catch (error) {
            console.warn('[AUTH] Error checking Supabase session:', error);
        }
    }

    if (hasValidSession) {
        // Verificar se o token é válido no backend
        try {
            const data = await api.get('/auth/status');
            if (data.aprovado) {
                window.location.href = 'dashboard.html';
            } else {
                ui.showAlert('Seu cadastro está aguardando aprovação do administrador.', 'warning');
                await logout(false); // Limpar sessão sem redirecionar
            }
        } catch (error) {
            console.warn('[AUTH] Session invalid:', error);
            await logout(false);
        }
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
    const policy = CONFIG.PASSWORD_POLICY || {
        min_length: 8,
        require_uppercase: true,
        require_lowercase: true,
        require_digit: true,
        require_special: true,
    };
    const minLength = policy.min_length || 8;

    if (!password || password.length < minLength) {
        errors.push(`Mínimo ${minLength} caracteres`);
    }
    if (policy.require_uppercase && !/[A-Z]/.test(password)) {
        errors.push('Pelo menos 1 letra maiúscula');
    }
    if (policy.require_lowercase && !/[a-z]/.test(password)) {
        errors.push('Pelo menos 1 letra minúscula');
    }
    if (policy.require_digit && !/[0-9]/.test(password)) {
        errors.push('Pelo menos 1 número');
    }
    if (policy.require_special && !/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;'`~]/.test(password)) {
        errors.push('Pelo menos 1 caractere especial');
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
 * Realiza login usando Supabase Auth
 */
async function loginWithSupabase(email, password) {
    if (!isSupabaseAvailable()) {
        throw new Error('Serviço de autenticação não disponível. Tente novamente mais tarde.');
    }

    const client = getSupabaseClient();

    const { data, error } = await client.auth.signInWithPassword({
        email: email,
        password: password
    });

    if (error) {
        // Traduzir mensagens de erro comuns
        if (error.message.includes('Invalid login credentials')) {
            throw new Error('Email ou senha incorretos');
        }
        if (error.message.includes('Email not confirmed')) {
            throw new Error('Email não confirmado. Verifique sua caixa de entrada.');
        }
        throw new Error(error.message || 'Erro ao fazer login');
    }

    return data;
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
            // Login via Supabase Auth
            await loginWithSupabase(email, senha);
            console.log('[AUTH] Login via Supabase successful');

            // Verificar status do usuário no backend
            const status = await api.get('/auth/status');

            if (status.aprovado) {
                ui.showAlert('Login realizado com sucesso!', 'success');
                setTimeout(() => {
                    window.location.href = 'dashboard.html';
                }, CONFIG.TIMEOUTS.REDIRECT_DELAY);
            } else {
                ui.showAlert('Seu cadastro está aguardando aprovação do administrador.', 'warning');
                await logout(false);
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
            // O registro é sempre feito via API backend
            // O backend cria o usuário no Supabase e localmente
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
 * Limpa todos os dados de autenticação (Supabase + localStorage)
 * @returns {Promise<void>}
 */
async function clearAllAuthData() {
    // 1. Limpar sessão Supabase via API
    if (isSupabaseAvailable()) {
        try {
            await getSupabaseClient().auth.signOut({ scope: 'local' });
        } catch (error) {
            console.warn('[AUTH] Error signing out from Supabase:', error);
        }
    }

    // 2. Limpar tokens da aplicação
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    localStorage.removeItem(CONFIG.USER_KEY);

    // 3. Limpar todas as chaves do Supabase no localStorage
    // Supabase armazena sessão com padrão: sb-{project-ref}-auth-token
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.startsWith('sb-') || key.startsWith('supabase'))) {
            keysToRemove.push(key);
        }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));

    console.log('[AUTH] All auth data cleared');
}

/**
 * Faz logout do usuário
 * @param {boolean} redirect - Se deve redirecionar para login
 */
async function logout(redirect = true) {
    await clearAllAuthData();

    if (redirect) {
        window.location.href = 'index.html';
    }
}

/**
 * Configura password toggle buttons via event delegation (pagina de login)
 */
function setupPasswordToggles() {
    document.querySelectorAll('.password-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const wrapper = btn.closest('.password-wrapper');
            const input = wrapper ? wrapper.querySelector('input') : null;
            if (input) togglePassword(input.id, btn);
        });
    });
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
