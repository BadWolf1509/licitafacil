/* JavaScript especifico do painel administrativo */

document.addEventListener('DOMContentLoaded', () => {
    verificarAdmin();
    setupTabs();
    carregarEstatisticas();
    carregarUsuariosPendentes();
    carregarTodosUsuarios();
});

async function verificarAdmin() {
    try {
        const status = await api.get('/auth/status');
        if (!status.admin) {
            ui.showAlert('Acesso restrito a administradores', 'error');
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 2000);
        }
    } catch (error) {
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
    try {
        const stats = await api.get('/admin/estatisticas');
        document.getElementById('statTotal').textContent = stats.total_usuarios;
        document.getElementById('statAprovados').textContent = stats.usuarios_aprovados;
        document.getElementById('statPendentes').textContent = stats.usuarios_pendentes;
        document.getElementById('statInativos').textContent = stats.usuarios_inativos;
    } catch (error) {
        console.error('Erro ao carregar estatisticas:', error);
    }
}

async function carregarUsuariosPendentes() {
    try {
        const usuarios = await api.get('/admin/usuarios/pendentes');
        const container = document.getElementById('listaPendentes');

        if (usuarios.length === 0) {
            container.innerHTML = '<div class="empty-state">Nenhum usuario pendente de aprovacao.</div>';
            return;
        }

        container.innerHTML = usuarios.map(u => `
            <div class="user-card">
                <div class="user-info">
                    <h4>${u.nome}</h4>
                    <p class="text-muted">${u.email}</p>
                    <small class="text-muted">Cadastrado em: ${formatarData(u.created_at)}</small>
                </div>
                <div class="user-actions">
                    <button class="btn btn-success btn-sm" onclick="aprovarUsuario(${u.id})">Aprovar</button>
                    <button class="btn btn-danger btn-sm" onclick="rejeitarUsuario(${u.id})">Rejeitar</button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        ui.showAlert('Erro ao carregar usuarios pendentes', 'error');
    }
}

async function carregarTodosUsuarios() {
    try {
        const usuarios = await api.get('/admin/usuarios');
        const container = document.getElementById('listaTodos');

        if (usuarios.length === 0) {
            container.innerHTML = '<div class="empty-state">Nenhum usuario cadastrado.</div>';
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
                if (!u.is_approved && u.is_active) {
                    actions = `
                        <button class="btn btn-success btn-sm" onclick="aprovarUsuario(${u.id})">Aprovar</button>
                        <button class="btn btn-danger btn-sm" onclick="rejeitarUsuario(${u.id})">Rejeitar</button>
                    `;
                } else if (!u.is_active) {
                    actions = `<button class="btn btn-outline btn-sm" onclick="reativarUsuario(${u.id})">Reativar</button>`;
                } else {
                    actions = `<button class="btn btn-danger btn-sm" onclick="rejeitarUsuario(${u.id})">Desativar</button>`;
                }
            }

            return `
                <div class="user-card">
                    <div class="user-info">
                        <h4>${u.nome} ${statusBadge}</h4>
                        <p class="text-muted">${u.email}</p>
                        <small class="text-muted">Cadastrado em: ${formatarData(u.created_at)}</small>
                    </div>
                    <div class="user-actions">
                        ${actions}
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        ui.showAlert('Erro ao carregar usuarios', 'error');
    }
}

async function aprovarUsuario(id) {
    try {
        await api.post(`/admin/usuarios/${id}/aprovar`);
        ui.showAlert('Usuario aprovado com sucesso!', 'success');
        carregarEstatisticas();
        carregarUsuariosPendentes();
        carregarTodosUsuarios();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao aprovar usuario', 'error');
    }
}

async function rejeitarUsuario(id) {
    if (!confirm('Tem certeza que deseja desativar este usuario?')) return;

    try {
        await api.post(`/admin/usuarios/${id}/rejeitar`);
        ui.showAlert('Usuario desativado com sucesso!', 'success');
        carregarEstatisticas();
        carregarUsuariosPendentes();
        carregarTodosUsuarios();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao desativar usuario', 'error');
    }
}

async function reativarUsuario(id) {
    try {
        await api.post(`/admin/usuarios/${id}/reativar`);
        ui.showAlert('Usuario reativado com sucesso!', 'success');
        carregarEstatisticas();
        carregarTodosUsuarios();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao reativar usuario', 'error');
    }
}
