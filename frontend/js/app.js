// LicitaFácil - Aplicação Principal

document.addEventListener('DOMContentLoaded', () => {
    // Verificar autenticação
    verificarAutenticacao();

    // Carregar dados do dashboard se estiver na página
    if (window.location.pathname.includes('dashboard')) {
        carregarDashboard();
    }
});

/**
 * Verifica se o usuário está autenticado
 */
async function verificarAutenticacao() {
    const token = localStorage.getItem(CONFIG.TOKEN_KEY);

    if (!token) {
        window.location.href = 'index.html';
        return;
    }

    try {
        const status = await api.get('/auth/status');

        if (!status.aprovado) {
            ui.showAlert('Seu cadastro está aguardando aprovação do administrador.', 'warning');
            setTimeout(() => {
                localStorage.removeItem(CONFIG.TOKEN_KEY);
                window.location.href = 'index.html';
            }, 3000);
            return;
        }

        // Atualizar nome do usuário
        const userName = document.getElementById('userName');
        if (userName) {
            userName.textContent = status.nome;
        }

        // Mostrar link de admin se for administrador
        if (status.admin) {
            const adminLink = document.getElementById('adminLink');
            if (adminLink) {
                adminLink.classList.remove('hidden');
            }
        }

    } catch (error) {
        console.error('Erro ao verificar autenticação:', error);
        localStorage.removeItem(CONFIG.TOKEN_KEY);
        window.location.href = 'index.html';
    }
}

/**
 * Carrega os dados do dashboard
 */
async function carregarDashboard() {
    try {
        // Carregar atestados
        const atestadosResp = await api.get('/atestados/');
        const atestados = atestadosResp.items || [];
        document.getElementById('totalAtestados').textContent = atestadosResp.total || atestados.length;

        // Carregar análises
        const analisesResp = await api.get('/analises/');
        const analises = analisesResp.items || [];
        document.getElementById('totalAnalises').textContent = analisesResp.total || analises.length;

        // Contar licitações atendidas
        const atendidas = analises.filter(a =>
            a.resultado_json?.some(r => r.status === 'atende')
        ).length;
        document.getElementById('licitacoesAtendidas').textContent = atendidas;

        // Mostrar análises recentes
        const recentList = document.getElementById('recentAnalises');
        if (analises.length === 0) {
            recentList.innerHTML = '<li class="recent-item text-muted">Nenhuma análise realizada ainda.</li>';
        } else {
            recentList.innerHTML = analises.slice(0, 5).map(a => `
                <li class="recent-item">
                    <div>
                        <strong>${a.nome_licitacao}</strong>
                        <br>
                        <small class="text-muted">${formatarData(a.created_at)}</small>
                    </div>
                    <a href="analises.html?id=${a.id}" class="btn btn-outline btn-sm">Ver</a>
                </li>
            `).join('');
        }

    } catch (error) {
        console.error('Erro ao carregar dashboard:', error);
        ui.showAlert('Erro ao carregar dados do dashboard', 'error');
    }
}

/**
 * Abre um modal pelo ID
 */
function abrirModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
}

/**
 * Abre o modal de cadastro de atestado
 */
function abrirModalAtestado() {
    abrirModal('modalAtestado');
}

/**
 * Fecha um modal
 */
function fecharModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}

/**
 * Fecha todos os modais ativos
 */
function fecharTodosModais() {
    document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
}

/**
 * Alterna o tema claro/escuro
 */
function toggleTheme() {
    const newTheme = theme.toggle();

    // Atualizar preferência no servidor
    api.put('/auth/me', { tema_preferido: newTheme })
        .catch(() => { }); // Ignorar erros de atualização
}

/**
 * Formata uma data ISO para exibição
 */
function formatarData(dataISO) {
    if (!dataISO) return '-';
    const data = new Date(dataISO);
    return data.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Formata um número para exibição
 */
function formatarNumero(numero, decimais = 2) {
    if (numero === null || numero === undefined) return '-';
    const parsed = Number(numero);
    if (!Number.isFinite(parsed)) return '-';
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: decimais,
        maximumFractionDigits: decimais
    }).format(parsed);
}

// Fechar modal ao clicar fora
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});

// Fechar modal com ESC
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        fecharTodosModais();
    }
});
