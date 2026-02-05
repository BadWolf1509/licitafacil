// LicitaFácil - Página de Perfil

document.addEventListener('DOMContentLoaded', async () => {
    // Aguardar configuração de autenticação (app.js já verifica auth)
    await loadAuthConfig();

    carregarPerfil();
    setupFormPerfil();
    setupFormSenha();

    // Theme switch listener (substitui onchange inline)
    const inputTema = document.getElementById('inputTema');
    if (inputTema) inputTema.addEventListener('change', toggleThemeSwitch);
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

        // Validar complexidade da senha
        const validation = validatePassword(senhaNova);
        if (!validation.valid) {
            ui.showAlert('Senha inválida: ' + validation.errors.join(', '), 'error');
            return;
        }

        const btn = document.getElementById('btnAlterarSenha');
        ui.setButtonLoading(btn, true, 'btnAlterarSenhaText', 'btnAlterarSenhaSpinner');

        try {
            // Verificar se Supabase está disponível
            if (!isSupabaseAvailable()) {
                throw new Error('Serviço de autenticação não disponível. Tente novamente mais tarde.');
            }

            const client = getSupabaseClient();

            // Obter sessão atual para pegar o email
            const { data: { session } } = await client.auth.getSession();
            if (!session) {
                throw new Error('Sessão expirada. Faça login novamente.');
            }

            // Verificar senha atual reauthenticando
            const { error: signInError } = await client.auth.signInWithPassword({
                email: session.user.email,
                password: senhaAtual
            });

            if (signInError) {
                throw new Error('Senha atual incorreta');
            }

            // Alterar a senha via Supabase Auth
            const { error: updateError } = await client.auth.updateUser({
                password: senhaNova
            });

            if (updateError) {
                throw new Error(updateError.message || 'Erro ao alterar senha');
            }

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
