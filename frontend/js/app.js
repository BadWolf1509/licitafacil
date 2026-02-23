// LicitaFácil - Aplicação Principal

document.addEventListener('DOMContentLoaded', async () => {
    // Configurar handlers globais (event delegation para onclick inline)
    setupGlobalHandlers();

    // Configurar menu mobile + dropdowns
    setupMobileNav();
    setupDropdowns();

    // Aguardar configuração de autenticação carregar (inicializa Supabase)
    await loadAuthConfig();

    // Verificar autenticação
    await verificarAutenticacao();

    // Carregar dados do dashboard se estiver na página
    if (window.location.pathname.includes('dashboard')) {
        carregarDashboard();
        setupFormAtestadoDashboard();
        setupDashboardActions();
    }
});

/**
 * Configura handlers globais via event delegation.
 * Substitui onclick inline no HTML por listeners centralizados.
 */
function setupGlobalHandlers() {
    document.addEventListener('click', (e) => {
        // Logout
        const logoutEl = e.target.closest('.nav-logout');
        if (logoutEl) {
            e.preventDefault();
            logout();
            return;
        }

        // Modal close (X button)
        const closeBtn = e.target.closest('.modal-close');
        if (closeBtn) {
            const modal = closeBtn.closest('.modal');
            if (modal) fecharModal(modal.id);
            return;
        }

        // Modal dismiss (cancel/close buttons with data attribute)
        const dismissBtn = e.target.closest('[data-dismiss="modal"]');
        if (dismissBtn) {
            const modal = dismissBtn.closest('.modal');
            if (modal) fecharModal(modal.id);
            return;
        }

        // Password toggle
        const toggleBtn = e.target.closest('.password-toggle');
        if (toggleBtn) {
            const wrapper = toggleBtn.closest('.password-wrapper');
            const input = wrapper ? wrapper.querySelector('input') : null;
            if (input) togglePassword(input.id, toggleBtn);
            return;
        }
    });
}

/**
 * Configura o menu mobile (hamburger) com suporte a dropdowns accordion.
 */
function setupMobileNav() {
    const toggle = document.querySelector('.nav-toggle');
    const nav = document.getElementById('headerNav');

    if (!toggle || !nav) return;

    toggle.addEventListener('click', () => {
        const isOpen = nav.classList.toggle('active');
        toggle.classList.toggle('active');
        toggle.setAttribute('aria-expanded', isOpen);
        toggle.setAttribute('aria-label', isOpen ? 'Fechar menu' : 'Abrir menu');

        // Fechar dropdowns quando hamburger fecha
        if (!isOpen) {
            nav.querySelectorAll('.nav-dropdown.open').forEach(d => {
                d.classList.remove('open');
                const btn = d.querySelector('.nav-dropdown-toggle');
                if (btn) btn.setAttribute('aria-expanded', 'false');
            });
        }
    });

    // Fechar hamburger ao clicar em link real (nao dropdown toggle)
    nav.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (link && nav.contains(link)) {
            nav.classList.remove('active');
            toggle.classList.remove('active');
            toggle.setAttribute('aria-expanded', 'false');
        }
    });

    // Fechar ao clicar fora do menu
    document.addEventListener('click', (e) => {
        if (!nav.contains(e.target) && !toggle.contains(e.target) && nav.classList.contains('active')) {
            nav.classList.remove('active');
            toggle.classList.remove('active');
            toggle.setAttribute('aria-expanded', 'false');
        }
    });
}

/**
 * Configura dropdowns de navegacao (hover desktop, click, teclado).
 */
function setupDropdowns() {
    const isMobile = () => window.matchMedia('(max-width: 768px)').matches;

    function closeAllDropdowns(except) {
        document.querySelectorAll('.nav-dropdown.open').forEach(d => {
            if (d !== except) {
                d.classList.remove('open');
                const btn = d.querySelector('.nav-dropdown-toggle');
                if (btn) btn.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // Click delegation para toggles
    document.addEventListener('click', (e) => {
        const toggle = e.target.closest('.nav-dropdown-toggle');
        if (toggle) {
            e.preventDefault();
            e.stopPropagation();
            const dropdown = toggle.closest('.nav-dropdown');
            if (!dropdown) return;

            const isOpen = dropdown.classList.contains('open');
            closeAllDropdowns(dropdown);
            dropdown.classList.toggle('open', !isOpen);
            toggle.setAttribute('aria-expanded', String(!isOpen));
            return;
        }

        // Click fora fecha todos
        if (!e.target.closest('.nav-dropdown')) {
            closeAllDropdowns();
        }
    });

    // Desktop: hover abre/fecha
    document.querySelectorAll('.nav-dropdown').forEach(dropdown => {
        let hoverTimeout;

        dropdown.addEventListener('mouseenter', () => {
            if (isMobile()) return;
            clearTimeout(hoverTimeout);
            closeAllDropdowns(dropdown);
            dropdown.classList.add('open');
            const btn = dropdown.querySelector('.nav-dropdown-toggle');
            if (btn) btn.setAttribute('aria-expanded', 'true');
        });

        dropdown.addEventListener('mouseleave', () => {
            if (isMobile()) return;
            hoverTimeout = setTimeout(() => {
                dropdown.classList.remove('open');
                const btn = dropdown.querySelector('.nav-dropdown-toggle');
                if (btn) btn.setAttribute('aria-expanded', 'false');
            }, 150);
        });
    });

    // Navegacao por teclado
    document.addEventListener('keydown', (e) => {
        const activeDropdown = document.querySelector('.nav-dropdown.open');
        if (!activeDropdown) return;

        const items = activeDropdown.querySelectorAll('.nav-dropdown-menu a');
        if (items.length === 0) return;

        const currentIndex = Array.from(items).indexOf(document.activeElement);

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (currentIndex < 0) items[0].focus();
            else if (currentIndex < items.length - 1) items[currentIndex + 1].focus();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (currentIndex > 0) items[currentIndex - 1].focus();
            else activeDropdown.querySelector('.nav-dropdown-toggle')?.focus();
        } else if (e.key === 'Escape') {
            activeDropdown.classList.remove('open');
            const btn = activeDropdown.querySelector('.nav-dropdown-toggle');
            if (btn) {
                btn.setAttribute('aria-expanded', 'false');
                btn.focus();
            }
        }
    });
}

/**
 * Configura event listeners para os action cards do dashboard
 */
function setupDashboardActions() {
    const actionAtestado = document.getElementById('actionCadastrarAtestado');
    if (actionAtestado) {
        const handler = () => abrirModalAtestado();
        actionAtestado.addEventListener('click', handler);
        actionAtestado.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); }
        });
    }

    const actionAnalise = document.getElementById('actionNovaAnalise');
    if (actionAnalise) {
        const handler = () => { window.location.href = 'analises.html'; };
        actionAnalise.addEventListener('click', handler);
        actionAnalise.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); }
        });
    }
}

/**
 * Configura o formulário de cadastro rápido de atestado no dashboard
 */
function setupFormAtestadoDashboard() {
    const form = document.getElementById('formAtestado');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const button = form.querySelector('button[type="submit"]');
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = 'Cadastrando...';

        const dados = {
            descricao_servico: document.getElementById('atDescricao').value,
            quantidade: parseFloat(document.getElementById('atQuantidade').value) || null,
            unidade: document.getElementById('atUnidade').value || null,
            contratante: document.getElementById('atContratante').value || null,
            data_emissao: document.getElementById('atDataEmissao').value || null
        };

        try {
            await api.post('/atestados/', dados);
            ui.showAlert('Atestado cadastrado com sucesso!', 'success');
            fecharModal('modalAtestado');
            form.reset();
            carregarDashboard(); // Atualizar contadores
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao cadastrar atestado', 'error');
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    });
}

/**
 * Verifica se o usuário está autenticado
 */
async function verificarAutenticacao() {
    // Verificar sessão Supabase
    let hasSession = false;

    if (isSupabaseAvailable()) {
        try {
            const { data: { session } } = await getSupabaseClient().auth.getSession();
            hasSession = !!session;
        } catch (error) {
            console.warn('[APP] Erro ao verificar sessão Supabase:', error);
        }
    }

    if (!hasSession) {
        // Limpar qualquer dado residual antes de redirecionar
        await clearSessionData();
        window.location.href = 'index.html';
        return;
    }

    try {
        const status = await api.get('/auth/status');

        if (!status.aprovado) {
            ui.showAlert('Seu cadastro está aguardando aprovação do administrador.', 'warning');
            // Limpar sessão completamente e redirecionar
            setTimeout(async () => {
                await clearSessionData();
                window.location.href = 'index.html';
            }, CONFIG.TIMEOUTS.POLLING_INTERVAL);
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
        // Limpar sessão completamente em caso de erro
        await clearSessionData();
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

        // Contar licitações atendidas (todas as exigências devem ser atendidas)
        const atendidas = analises.filter(a =>
            a.resultado_json && a.resultado_json.length > 0 &&
            a.resultado_json.every(r => r.status === 'atende')
        ).length;
        document.getElementById('licitacoesAtendidas').textContent = atendidas;

        // Mostrar análises recentes
        const recentList = document.getElementById('recentAnalises');
        if (analises.length === 0) {
            recentList.innerHTML = '<li class="recent-item text-muted">Nenhuma análise realizada ainda.</li>';
        } else {
            recentList.innerHTML = analises.slice(0, 5).map(a => {
                let statusBadge = '';
                if (a.resultado_json && a.resultado_json.length > 0) {
                    const allMet = a.resultado_json.every(r => r.status === 'atende');
                    const anyMet = a.resultado_json.some(r => r.status === 'atende');
                    if (allMet) {
                        statusBadge = '<span class="badge badge-success">Atende</span>';
                    } else if (anyMet) {
                        statusBadge = '<span class="badge badge-warning">Parcial</span>';
                    } else {
                        statusBadge = '<span class="badge badge-error">Não Atende</span>';
                    }
                }
                return `
                <li class="recent-item">
                    <div>
                        <strong>${Sanitize.escapeHtml(a.nome_licitacao)}</strong> ${statusBadge}
                        <br>
                        <small class="text-muted">${formatarData(a.created_at)}</small>
                    </div>
                    <a href="analises.html?id=${a.id}" class="btn btn-outline btn-sm">Ver</a>
                </li>`;
            }).join('');
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
    if (!modal) return;
    modal.classList.add('active');

    // Focus first input/button inside modal
    requestAnimationFrame(() => {
        const focusable = modal.querySelector('input:not([type="hidden"]), textarea, select, button:not(.modal-close)');
        if (focusable) focusable.focus();
    });

    // Focus trap: Tab/Shift+Tab cycles within modal
    const trapHandler = (e) => {
        if (e.key !== 'Tab') return;
        const focusableEls = modal.querySelectorAll(
            'input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusableEls.length === 0) return;
        const first = focusableEls[0];
        const last = focusableEls[focusableEls.length - 1];
        if (e.shiftKey) {
            if (document.activeElement === first) { e.preventDefault(); last.focus(); }
        } else {
            if (document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
    };
    modal._focusTrapHandler = trapHandler;
    modal.addEventListener('keydown', trapHandler);
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
    if (!modal) return;
    modal.classList.remove('active');
    if (modal._focusTrapHandler) {
        modal.removeEventListener('keydown', modal._focusTrapHandler);
        delete modal._focusTrapHandler;
    }
}

/**
 * Fecha todos os modais ativos
 */
function fecharTodosModais() {
    document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
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

/**
 * Exibe um modal de confirmacao customizado (substitui window.confirm)
 * @param {string} message - Mensagem de confirmacao
 * @param {Object} options - Opcoes opcionais
 * @param {string} options.title - Titulo do modal (default: 'Confirmar')
 * @param {string} options.confirmText - Texto do botao confirmar (default: 'Confirmar')
 * @param {string} options.cancelText - Texto do botao cancelar (default: 'Cancelar')
 * @param {string} options.type - Tipo: 'warning', 'danger' (default: 'warning')
 * @returns {Promise<boolean>} True se confirmado, False se cancelado
 */
function confirmAction(message, options = {}) {
    const {
        title = 'Confirmar',
        confirmText = 'Confirmar',
        cancelText = 'Cancelar',
        type = 'warning'
    } = options;

    return new Promise((resolve) => {
        const modalId = 'modalConfirmAction';

        // Remover modal anterior se existir
        const existing = document.getElementById(modalId);
        if (existing) existing.remove();

        const btnClass = type === 'danger' ? 'btn-danger' : 'btn-primary';

        const modal = document.createElement('div');
        modal.id = modalId;
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 420px;">
                <div class="modal-header">
                    <h3>${Sanitize.escapeHtml(title)}</h3>
                    <button class="modal-close" aria-label="Fechar">&times;</button>
                </div>
                <div class="modal-body">
                    <p>${Sanitize.escapeHtml(message)}</p>
                </div>
                <div class="modal-footer" style="display:flex;gap:8px;justify-content:flex-end;">
                    <button class="btn btn-outline" data-confirm="cancel">${Sanitize.escapeHtml(cancelText)}</button>
                    <button class="btn ${btnClass}" data-confirm="ok">${Sanitize.escapeHtml(confirmText)}</button>
                </div>
            </div>
        `;

        const cleanup = (result) => {
            modal.remove();
            document.removeEventListener('keydown', escHandler);
            resolve(result);
        };

        const escHandler = (e) => {
            if (e.key === 'Escape') cleanup(false);
        };

        modal.addEventListener('click', (e) => {
            if (e.target === modal) cleanup(false);
            const btn = e.target.closest('[data-confirm]');
            if (!btn) {
                if (e.target.closest('.modal-close')) cleanup(false);
                return;
            }
            cleanup(btn.dataset.confirm === 'ok');
        });

        document.addEventListener('keydown', escHandler);
        document.body.appendChild(modal);

        // Focus no botao de cancelar (mais seguro)
        const cancelBtn = modal.querySelector('[data-confirm="cancel"]');
        if (cancelBtn) cancelBtn.focus();
    });
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
