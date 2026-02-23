/* JavaScript especifico do painel administrativo */

document.addEventListener('DOMContentLoaded', async () => {
    // Aguardar config carregar antes de fazer chamadas API
    await loadAuthConfig();

    setupAdminEventDelegation();
    verificarAdmin();
    setupTabs();
    carregarEstatisticas();
    carregarUsuariosPendentes();
    carregarTodosUsuarios();
});

function setupAdminEventDelegation() {
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        const userId = btn.dataset.userId ? parseInt(btn.dataset.userId, 10) : null;
        if (!userId) return;
        switch (action) {
            case 'aprovar': aprovarUsuario(userId); break;
            case 'rejeitar': rejeitarUsuario(userId); break;
            case 'reativar': reativarUsuario(userId); break;
            case 'excluir': excluirUsuario(userId, btn.dataset.userNome || ''); break;
        }
    });
}

async function verificarAdmin() {
    try {
        const status = await api.get('/auth/status');
        if (!status.admin) {
            ui.showAlert('Acesso restrito a administradores', 'error');
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, CONFIG.TIMEOUTS.INIT_DELAY);
        }
    } catch (error) {
        // Limpar sessão completamente antes de redirecionar
        await clearSessionData();
        window.location.href = 'index.html';
    }
}

function setupTabs() {
    const tabs = document.querySelectorAll('.tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;

            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            contents.forEach(c => {
                c.classList.remove('active');
                if (c.id === `tab-${targetTab}`) {
                    c.classList.add('active');
                }
            });
        });
    });
}

async function carregarEstatisticas() {
    const statIds = ['statTotal', 'statAprovados', 'statPendentes', 'statInativos'];
    statIds.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '...'; });

    try {
        const stats = await api.get('/admin/estatisticas');
        document.getElementById('statTotal').textContent = stats.total_usuarios;
        document.getElementById('statAprovados').textContent = stats.usuarios_aprovados;
        document.getElementById('statPendentes').textContent = stats.usuarios_pendentes;
        document.getElementById('statInativos').textContent = stats.usuarios_inativos;
    } catch (error) {
        console.error('Erro ao carregar estatisticas:', error);
        statIds.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '-'; });
    }
}

async function carregarUsuariosPendentes() {
    await ErrorHandler.withErrorHandling(async () => {
        const response = await api.get('/admin/usuarios/pendentes');
        const usuarios = response.items || response;
        const container = document.getElementById('listaPendentes');

        if (!usuarios || usuarios.length === 0) {
            container.innerHTML = '<div class="empty-state">Nenhum usuário pendente de aprovação.</div>';
            return;
        }

        container.innerHTML = usuarios.map(u => `
            <div class="user-card">
                <div class="user-info">
                    <h4>${Sanitize.escapeHtml(u.nome)}</h4>
                    <p class="text-muted">${Sanitize.escapeHtml(u.email)}</p>
                    <small class="text-muted">Cadastrado em: ${formatarData(u.created_at)}</small>
                </div>
                <div class="user-actions">
                    <button class="btn btn-success btn-sm" data-action="aprovar" data-user-id="${u.id}">Aprovar</button>
                    <button class="btn btn-danger btn-sm" data-action="rejeitar" data-user-id="${u.id}">Rejeitar</button>
                    <button class="btn btn-outline btn-sm" data-action="excluir" data-user-id="${u.id}" data-user-nome="${Sanitize.escapeHtml(u.nome)}">Excluir</button>
                </div>
            </div>
        `).join('');
    }, 'Erro ao carregar usuários pendentes', { container: 'listaPendentes' });
}

async function carregarTodosUsuarios() {
    await ErrorHandler.withErrorHandling(async () => {
        const response = await api.get('/admin/usuarios');
        const usuarios = response.items || response;
        const container = document.getElementById('listaTodos');

        if (!usuarios || usuarios.length === 0) {
            container.innerHTML = '<div class="empty-state">Nenhum usuário cadastrado.</div>';
            return;
        }

        container.innerHTML = usuarios.map(u => {
            let statusBadge = '';
            if (!u.is_active) {
                statusBadge = '<span class="badge badge-error">Inativo</span>';
            } else if (!u.is_approved) {
                statusBadge = '<span class="badge badge-warning">Pendente</span>';
            } else if (u.is_admin) {
                statusBadge = '<span class="badge badge-info">Admin</span>';
            } else {
                statusBadge = '<span class="badge badge-success">Ativo</span>';
            }

            let actions = '';
            if (!u.is_admin) {
                const htmlNome = Sanitize.escapeHtml(u.nome);
                if (!u.is_approved && u.is_active) {
                    actions = `
                        <button class="btn btn-success btn-sm" data-action="aprovar" data-user-id="${u.id}">Aprovar</button>
                        <button class="btn btn-danger btn-sm" data-action="rejeitar" data-user-id="${u.id}">Rejeitar</button>
                        <button class="btn btn-outline btn-sm" data-action="excluir" data-user-id="${u.id}" data-user-nome="${htmlNome}">Excluir</button>
                    `;
                } else if (!u.is_active) {
                    actions = `
                        <button class="btn btn-outline btn-sm" data-action="reativar" data-user-id="${u.id}">Reativar</button>
                        <button class="btn btn-outline btn-sm" data-action="excluir" data-user-id="${u.id}" data-user-nome="${htmlNome}">Excluir</button>
                    `;
                } else {
                    actions = `
                        <button class="btn btn-danger btn-sm" data-action="rejeitar" data-user-id="${u.id}">Desativar</button>
                        <button class="btn btn-outline btn-sm" data-action="excluir" data-user-id="${u.id}" data-user-nome="${htmlNome}">Excluir</button>
                    `;
                }
            }

            return `
                <div class="user-card">
                    <div class="user-info">
                        <h4>${Sanitize.escapeHtml(u.nome)} ${statusBadge}</h4>
                        <p class="text-muted">${Sanitize.escapeHtml(u.email)}</p>
                        <small class="text-muted">Cadastrado em: ${formatarData(u.created_at)}</small>
                    </div>
                    <div class="user-actions">
                        ${actions}
                    </div>
                </div>
            `;
        }).join('');
    }, 'Erro ao carregar usuários', { container: 'listaTodos' });
}

async function aprovarUsuario(id) {
    try {
        await api.post(`/admin/usuarios/${id}/aprovar`);
        ui.showAlert('Usuário aprovado com sucesso!', 'success');
        carregarEstatisticas();
        carregarUsuariosPendentes();
        carregarTodosUsuarios();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao aprovar usuário', 'error');
    }
}

async function rejeitarUsuario(id) {
    if (!await confirmAction('Tem certeza que deseja desativar este usuário?', { type: 'danger', confirmText: 'Desativar' })) return;

    try {
        await api.post(`/admin/usuarios/${id}/rejeitar`);
        ui.showAlert('Usuário desativado com sucesso!', 'success');
        carregarEstatisticas();
        carregarUsuariosPendentes();
        carregarTodosUsuarios();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao desativar usuário', 'error');
    }
}

async function reativarUsuario(id) {
    try {
        await api.post(`/admin/usuarios/${id}/reativar`);
        ui.showAlert('Usuário reativado com sucesso!', 'success');
        carregarEstatisticas();
        carregarTodosUsuarios();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao reativar usuário', 'error');
    }
}

async function excluirUsuario(id, nome) {
    if (!await confirmAction(`Deseja excluir permanentemente o usuário "${nome}"? Todos os dados associados serão perdidos.`, { title: 'Excluir usuário', type: 'danger', confirmText: 'Excluir' })) return;

    try {
        await api.delete(`/admin/usuarios/${id}`);
        ui.showAlert('Usuário excluído permanentemente!', 'success');
        carregarEstatisticas();
        carregarUsuariosPendentes();
        carregarTodosUsuarios();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao excluir usuário', 'error');
    }
}
