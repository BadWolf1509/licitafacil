// LicitaFácil - Página de Perfil

document.addEventListener('DOMContentLoaded', () => {
    verificarAutenticacao();
    carregarPerfil();
    setupFormPerfil();
    setupFormSenha();
});

/**
 * Carrega os dados do perfil do usuário
 */
async function carregarPerfil() {
    try {
        const usuario = await api.get('/auth/me');
        preencherPerfil(usuario);
    } catch (error) {
        ui.showAlert('Erro ao carregar perfil: ' + error.message, 'error');
    }
}

/**
 * Preenche os campos da página com os dados do usuário
 */
function preencherPerfil(usuario) {
    // Avatar com inicial do nome
    const avatar = document.getElementById('profileAvatar');
    if (avatar && usuario.nome) {
        avatar.textContent = usuario.nome.charAt(0).toUpperCase();
    }

    // Nome e email
    const nome = document.getElementById('profileName');
    if (nome) nome.textContent = usuario.nome;

    const email = document.getElementById('profileEmail');
    if (email) email.textContent = usuario.email;

    // Badges de status
    const badges = document.getElementById('profileBadges');
    if (badges) {
        badges.innerHTML = '';

        if (usuario.is_admin) {
            badges.innerHTML += '<span class="badge badge-info">Administrador</span>';
        }

        if (usuario.is_approved) {
            badges.innerHTML += '<span class="badge badge-success">Aprovado</span>';
        } else {
            badges.innerHTML += '<span class="badge badge-warning">Pendente</span>';
        }

        if (!usuario.is_active) {
            badges.innerHTML += '<span class="badge badge-error">Inativo</span>';
        }
    }

    // Data de criação
    const createdAt = document.getElementById('profileCreatedAt');
    if (createdAt && usuario.created_at) {
        createdAt.textContent = formatarData(usuario.created_at);
    }

    // Data de aprovação
    const approvedAt = document.getElementById('profileApprovedAt');
    if (approvedAt) {
        if (usuario.approved_at) {
            approvedAt.textContent = 'Aprovado em: ' + formatarData(usuario.approved_at);
        } else {
            approvedAt.textContent = '';
        }
    }

    // Preencher formulário de edição
    const inputNome = document.getElementById('inputNome');
    if (inputNome) inputNome.value = usuario.nome;

    // Sincronizar switch de tema com o tema atual
    const inputTema = document.getElementById('inputTema');
    if (inputTema) {
        const currentTheme = usuario.tema_preferido || theme.get() || 'light';
        inputTema.checked = currentTheme === 'dark';
    }
}

/**
 * Configura o formulário de edição de perfil
 */
function setupFormPerfil() {
    const form = document.getElementById('formPerfil');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const btn = document.getElementById('btnSalvarPerfil');
        ui.setButtonLoading(btn, true, 'btnSalvarPerfilText', 'btnSalvarPerfilSpinner');

        try {
            const dados = {
                nome: document.getElementById('inputNome').value
            };

            const usuario = await api.put('/auth/me', dados);

            // Atualizar dados exibidos
            preencherPerfil(usuario);

            // Atualizar nome no localStorage para outras páginas
            const userData = JSON.parse(localStorage.getItem(CONFIG.USER_KEY) || '{}');
            userData.nome = usuario.nome;
            localStorage.setItem(CONFIG.USER_KEY, JSON.stringify(userData));

            ui.showAlert('Nome atualizado com sucesso!', 'success');
        } catch (error) {
            ui.showAlert('Erro ao salvar perfil: ' + error.message, 'error');
        } finally {
            ui.setButtonLoading(btn, false, 'btnSalvarPerfilText', 'btnSalvarPerfilSpinner');
        }
    });
}

/**
 * Alterna o tema via switch toggle (aplicação imediata)
 */
async function toggleThemeSwitch() {
    const inputTema = document.getElementById('inputTema');
    if (!inputTema) return;

    const newTheme = inputTema.checked ? 'dark' : 'light';

    // Aplicar tema imediatamente
    theme.set(newTheme);

    // Salvar no servidor em background
    try {
        await api.put('/auth/me', { tema_preferido: newTheme });
    } catch (error) {
        // Silencioso - o tema já foi aplicado localmente
        console.error('Erro ao salvar tema:', error);
    }
}

/**
 * Configura o formulário de alteração de senha
 */
function setupFormSenha() {
    const form = document.getElementById('formSenha');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const senhaAtual = document.getElementById('inputSenhaAtual').value;
        const senhaNova = document.getElementById('inputSenhaNova').value;
        const confirmarSenha = document.getElementById('inputConfirmarSenha').value;

        // Validar senhas iguais
        if (senhaNova !== confirmarSenha) {
            ui.showAlert('As senhas não coincidem', 'error');
            return;
        }

        // Validar tamanho mínimo
        if (senhaNova.length < 6) {
            ui.showAlert('A nova senha deve ter pelo menos 6 caracteres', 'error');
            return;
        }

        const btn = document.getElementById('btnAlterarSenha');
        ui.setButtonLoading(btn, true, 'btnAlterarSenhaText', 'btnAlterarSenhaSpinner');

        try {
            await api.post('/auth/change-password', {
                senha_atual: senhaAtual,
                senha_nova: senhaNova,
                confirmar_senha: confirmarSenha
            });

            ui.showAlert('Senha alterada com sucesso!', 'success');

            // Limpar formulário
            form.reset();
        } catch (error) {
            ui.showAlert(error.message, 'error');
        } finally {
            ui.setButtonLoading(btn, false, 'btnAlterarSenhaText', 'btnAlterarSenhaSpinner');
        }
    });
}

/**
 * Toggle de visibilidade da senha
 */
function togglePassword(inputId, button) {
    const input = document.getElementById(inputId);
    if (!input) return;

    if (input.type === 'password') {
        input.type = 'text';
        button.querySelector('.eye-icon').textContent = '🙈';
    } else {
        input.type = 'password';
        button.querySelector('.eye-icon').textContent = '👁';
    }
}
