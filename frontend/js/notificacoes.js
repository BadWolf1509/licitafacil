/**
 * Componente global de notificacoes (sino).
 * Carregado em todas as paginas autenticadas.
 */
const NotificacoesModule = {
    pollInterval: null,
    count: 0,
    isOpen: false,

    async init() {
        this.renderBell();
        this.setupEvents();
        // Aguardar auth config antes de fazer chamadas API
        // (evita race condition: supabaseClient pode nao estar pronto)
        await loadAuthConfig();
        this.loadCount();
        this.startPolling();
    },

    renderBell() {
        const nav = document.querySelector('.header-nav');
        if (!nav) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'notification-bell-wrapper';
        wrapper.innerHTML = `
            <button class="notification-bell" aria-label="Notificações" data-action="toggle-notif">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                    <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
                </svg>
                <span class="notification-badge hidden" id="notifBadge">0</span>
            </button>
            <div class="notification-dropdown hidden" id="notifDropdown">
                <div class="notif-header">
                    <span>Notificações</span>
                    <button class="btn btn-sm btn-outline" data-action="marcar-todas-lidas">Marcar todas</button>
                </div>
                <div class="notif-list" id="notifList">
                    <p class="text-muted" style="padding: 1rem; text-align: center;">Nenhuma notificação</p>
                </div>
                <a href="calendario.html" class="notif-footer">Ver calendário</a>
            </div>
        `;

        // Inserir no .nav-utility como primeiro filho, ou antes do .nav-logout (fallback)
        const utility = nav.querySelector('.nav-utility');
        if (utility) {
            utility.insertBefore(wrapper, utility.firstChild);
        } else {
            const logoutLink = nav.querySelector('.nav-logout');
            if (logoutLink) logoutLink.parentNode.insertBefore(wrapper, logoutLink);
        }
    },

    setupEvents() {
        document.addEventListener('click', (e) => {
            const action = e.target.closest('[data-action]');
            if (!action) {
                // Fechar dropdown se clicar fora
                if (this.isOpen && !e.target.closest('.notification-bell-wrapper')) {
                    this.closeDropdown();
                }
                return;
            }

            const actionName = action.dataset.action;
            if (actionName === 'toggle-notif') {
                e.preventDefault();
                this.toggleDropdown();
            } else if (actionName === 'marcar-todas-lidas') {
                e.preventDefault();
                this.marcarTodasLidas();
            } else if (actionName === 'marcar-lida') {
                e.preventDefault();
                const id = action.dataset.id;
                if (id) this.marcarLida(id);
            }
        });
    },

    async loadCount() {
        try {
            const resp = await api.get('/notificacoes/nao-lidas/count');
            this.count = resp.count || 0;
            this.updateBadge();
        } catch {
            // Silenciar erros de polling
        }
    },

    updateBadge() {
        const badge = document.getElementById('notifBadge');
        if (!badge) return;

        if (this.count > 0) {
            badge.textContent = this.count > 99 ? '99+' : String(this.count);
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    },

    startPolling() {
        this.pollInterval = setInterval(() => this.loadCount(), 30000);
    },

    async toggleDropdown() {
        const dropdown = document.getElementById('notifDropdown');
        if (!dropdown) return;

        if (this.isOpen) {
            this.closeDropdown();
        } else {
            dropdown.classList.remove('hidden');
            this.isOpen = true;
            await this.loadNotificacoes();
        }
    },

    closeDropdown() {
        const dropdown = document.getElementById('notifDropdown');
        if (dropdown) dropdown.classList.add('hidden');
        this.isOpen = false;
    },

    async loadNotificacoes() {
        const list = document.getElementById('notifList');
        if (!list) return;

        try {
            const resp = await api.get('/notificacoes/?page_size=5');
            const items = resp.items || [];

            if (items.length === 0) {
                list.innerHTML = '<p class="text-muted" style="padding: 1rem; text-align: center;">Nenhuma notificação</p>';
                return;
            }

            list.innerHTML = items.map(n => {
                const titulo = Sanitize.escapeHtml(n.titulo);
                const mensagem = Sanitize.escapeHtml(n.mensagem);
                const unreadClass = n.lida ? '' : ' unread';
                const data = new Date(n.created_at).toLocaleString('pt-BR', {
                    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                });
                return `
                    <div class="notif-item${unreadClass}" data-action="marcar-lida" data-id="${n.id}">
                        <div class="notif-item-title">${titulo}</div>
                        <div class="notif-item-msg">${mensagem}</div>
                        <div class="notif-item-date">${Sanitize.escapeHtml(data)}</div>
                    </div>
                `;
            }).join('');
        } catch {
            list.innerHTML = '<p class="text-muted" style="padding: 1rem; text-align: center;">Erro ao carregar</p>';
        }
    },

    async marcarLida(id) {
        try {
            await api.patch(`/notificacoes/${id}/lida`);
            this.loadCount();
            this.loadNotificacoes();
        } catch {
            // Silenciar
        }
    },

    async marcarTodasLidas() {
        try {
            await api.post('/notificacoes/marcar-todas-lidas');
            this.count = 0;
            this.updateBadge();
            this.loadNotificacoes();
        } catch {
            // Silenciar
        }
    },
};

// Auto-init apos DOMContentLoaded (se autenticado)
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.header-nav')) {
        NotificacoesModule.init();
    }
});
