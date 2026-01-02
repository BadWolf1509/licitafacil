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
 * Configura o formulário de login
 */
function setupLoginForm() {
    const form = document.getElementById('loginForm');
    const button = form.querySelector('button[type="submit"]');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const email = document.getElementById('loginEmail').value;
        const senha = document.getElementById('loginSenha').value;

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

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const nome = document.getElementById('registroNome').value;
        const email = document.getElementById('registroEmail').value;
        const senha = document.getElementById('registroSenha').value;
        const confirmarSenha = document.getElementById('registroConfirmarSenha').value;

        // Validações
        if (senha !== confirmarSenha) {
            ui.showAlert('As senhas não coincidem', 'error');
            return;
        }

        if (senha.length < 6) {
            ui.showAlert('A senha deve ter no mínimo 6 caracteres', 'error');
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
