// LicitaFacil - Modulo de Licitacoes
// Gerencia CRUD, filtros, status, tags e historico de licitacoes

const STATUS_LABELS = {
    identificada: 'Identificada',
    em_analise: 'Em Análise',
    go_nogo: 'GO/NO-GO',
    elaborando_proposta: 'Elaborando Proposta',
    proposta_enviada: 'Proposta Enviada',
    em_disputa: 'Em Disputa',
    vencida: 'Vencida',
    perdida: 'Perdida',
    contrato_assinado: 'Contrato Assinado',
    em_execucao: 'Em Execução',
    concluida: 'Concluída',
    desistida: 'Desistida',
    cancelada: 'Cancelada',
};

const STATUS_TRANSITIONS = {
    identificada: ['em_analise', 'desistida', 'cancelada'],
    em_analise: ['go_nogo', 'desistida', 'cancelada'],
    go_nogo: ['elaborando_proposta', 'desistida', 'cancelada'],
    elaborando_proposta: ['proposta_enviada', 'desistida', 'cancelada'],
    proposta_enviada: ['em_disputa', 'desistida', 'cancelada'],
    em_disputa: ['vencida', 'perdida', 'cancelada'],
    vencida: ['contrato_assinado', 'cancelada'],
    perdida: [],
    contrato_assinado: ['em_execucao', 'cancelada'],
    em_execucao: ['concluida', 'cancelada'],
    concluida: [],
    desistida: [],
    cancelada: [],
};

const LicitacoesModule = {
    // Estado
    filtros: { status: '', uf: '', modalidade: '', busca: '' },
    paginaAtual: 1,
    licitacaoAtual: null,

    init() {
        this.carregarEstatisticas();
        this.carregarLicitacoes();
        this.setupFiltros();
        this.setupForms();

        // Verificar se ha ID na URL
        const params = new URLSearchParams(window.location.search);
        const id = params.get('id');
        if (id) {
            this.carregarDetalhe(id);
        }
    },

    // === ESTATISTICAS ===

    async carregarEstatisticas() {
        try {
            const stats = await api.get('/licitacoes/estatisticas');
            const container = document.getElementById('statsContainer');
            if (!container) return;

            const statusAtivos = Object.entries(stats.por_status || {})
                .filter(([s]) => !['concluida', 'cancelada', 'desistida', 'perdida'].includes(s))
                .reduce((sum, [, count]) => sum + count, 0);

            container.innerHTML = `
                <div class="card stat-card">
                    <div class="stat-value">${stats.total || 0}</div>
                    <div class="stat-label">Total</div>
                </div>
                <div class="card stat-card">
                    <div class="stat-value">${statusAtivos}</div>
                    <div class="stat-label">Ativas</div>
                </div>
                <div class="card stat-card">
                    <div class="stat-value">${stats.por_status?.vencida || 0}</div>
                    <div class="stat-label">Vencidas</div>
                </div>
                <div class="card stat-card">
                    <div class="stat-value">${Object.keys(stats.por_uf || {}).length}</div>
                    <div class="stat-label">UFs</div>
                </div>
            `;
        } catch (error) {
            console.warn('Erro ao carregar estatisticas:', error);
        }
    },

    // === LISTAGEM ===

    async carregarLicitacoes(page) {
        if (page) this.paginaAtual = page;

        await ErrorHandler.withErrorHandling(async () => {
            const params = new URLSearchParams({
                page: this.paginaAtual,
                page_size: 10,
            });
            if (this.filtros.status) params.set('status', this.filtros.status);
            if (this.filtros.uf) params.set('uf', this.filtros.uf);
            if (this.filtros.modalidade) params.set('modalidade', this.filtros.modalidade);
            if (this.filtros.busca) params.set('busca', this.filtros.busca);

            const response = await api.get(`/licitacoes/?${params}`);
            this.renderLista(response);
            this.renderPaginacao(response);
        }, 'Erro ao carregar licitações', { container: 'listaLicitacoes' });
    },

    renderLista(response) {
        const container = document.getElementById('listaLicitacoes');
        const licitacoes = response.items || [];

        if (licitacoes.length === 0) {
            container.innerHTML = `
                <div class="card empty-state">
                    <h3>Nenhuma licitação encontrada</h3>
                    <p class="text-muted">Crie sua primeira licitação clicando no botão acima</p>
                </div>
            `;
            return;
        }

        container.innerHTML = licitacoes.map(l => {
            const statusLabel = STATUS_LABELS[l.status] || l.status;
            const tagsHtml = (l.tags || []).map(t =>
                `<span class="tag-chip">${Sanitize.escapeHtml(t.tag)}</span>`
            ).join('');

            const valorStr = l.valor_estimado
                ? `R$ ${Number(l.valor_estimado).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                : '';

            const dataStr = l.data_abertura
                ? new Date(l.data_abertura).toLocaleDateString('pt-BR')
                : '';

            return `
                <div class="card licitacao-card">
                    <div class="licitacao-card-header">
                        <div class="licitacao-card-info">
                            <h3>${Sanitize.escapeHtml(l.numero)} - ${Sanitize.escapeHtml(l.orgao)}</h3>
                            <p class="text-muted" style="margin: 4px 0;">${Sanitize.escapeHtml(l.objeto.substring(0, 150))}${l.objeto.length > 150 ? '...' : ''}</p>
                            <div class="licitacao-card-meta">
                                <span class="status-badge status-badge-${l.status}">${statusLabel}</span>
                                <span>${Sanitize.escapeHtml(l.modalidade)}</span>
                                ${l.uf ? `<span>${Sanitize.escapeHtml(l.uf)}</span>` : ''}
                                ${valorStr ? `<span class="valor-currency">${valorStr}</span>` : ''}
                                ${dataStr ? `<span>Abertura: ${dataStr}</span>` : ''}
                            </div>
                            ${tagsHtml ? `<div class="licitacao-card-tags">${tagsHtml}</div>` : ''}
                        </div>
                        <div class="licitacao-card-actions">
                            <button class="btn btn-primary btn-sm" data-action="ver-detalhe" data-id="${l.id}">Ver</button>
                            <button class="btn btn-danger btn-sm" data-action="excluir" data-id="${l.id}">Excluir</button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    },

    renderPaginacao(response) {
        const container = document.getElementById('paginacao');
        if (!container) return;

        const totalPages = response.total_pages || 1;
        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        let html = '';
        if (this.paginaAtual > 1) {
            html += `<button class="btn btn-outline btn-sm" data-action="pagina" data-page="${this.paginaAtual - 1}">Anterior</button>`;
        }
        for (let i = 1; i <= totalPages; i++) {
            const active = i === this.paginaAtual ? 'btn-primary' : 'btn-outline';
            html += `<button class="btn ${active} btn-sm" data-action="pagina" data-page="${i}">${i}</button>`;
        }
        if (this.paginaAtual < totalPages) {
            html += `<button class="btn btn-outline btn-sm" data-action="pagina" data-page="${this.paginaAtual + 1}">Próximo</button>`;
        }
        container.innerHTML = html;
    },

    // === FILTROS ===

    setupFiltros() {
        const self = this;
        const debouncedLoad = ui.debounce(() => self.carregarLicitacoes(1), CONFIG.TIMEOUTS.DEBOUNCE_INPUT);

        document.getElementById('filtroStatus')?.addEventListener('change', function() {
            self.filtros.status = this.value;
            self.carregarLicitacoes(1);
        });
        document.getElementById('filtroUF')?.addEventListener('change', function() {
            self.filtros.uf = this.value;
            self.carregarLicitacoes(1);
        });
        document.getElementById('filtroModalidade')?.addEventListener('change', function() {
            self.filtros.modalidade = this.value;
            self.carregarLicitacoes(1);
        });
        document.getElementById('filtroBusca')?.addEventListener('input', function() {
            self.filtros.busca = this.value;
            debouncedLoad();
        });
    },

    // === CRUD ===

    setupForms() {
        const self = this;

        // Form criar
        document.getElementById('formNovaLicitacao')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const dados = Object.fromEntries(formData.entries());

            // Limpar campos vazios
            Object.keys(dados).forEach(k => {
                if (dados[k] === '') delete dados[k];
            });

            // Converter valor para numero
            if (dados.valor_estimado) dados.valor_estimado = parseFloat(dados.valor_estimado);

            const button = e.target.querySelector('button[type="submit"]');
            ui.setButtonLoading(button, true, 'btnCriarText', 'btnCriarSpinner');

            try {
                await api.post('/licitacoes/', dados);
                ui.showAlert('Licitação criada com sucesso!', 'success');
                fecharModal('modalNovaLicitacao');
                e.target.reset();
                self.carregarLicitacoes(1);
                self.carregarEstatisticas();
            } catch (error) {
                ui.showAlert(error.message || 'Erro ao criar licitação', 'error');
            } finally {
                ui.setButtonLoading(button, false, 'btnCriarText', 'btnCriarSpinner');
            }
        });

        // Form editar
        document.getElementById('formEditarLicitacao')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('editarId').value;
            const formData = new FormData(e.target);
            const dados = Object.fromEntries(formData.entries());
            delete dados.id;

            // Limpar campos vazios para nao sobrescrever
            Object.keys(dados).forEach(k => {
                if (dados[k] === '') delete dados[k];
            });

            // Converter valores numericos
            ['valor_estimado', 'valor_homologado', 'valor_proposta'].forEach(f => {
                if (dados[f]) dados[f] = parseFloat(dados[f]);
            });

            const button = e.target.querySelector('button[type="submit"]');
            ui.setButtonLoading(button, true, 'btnEditarText', 'btnEditarSpinner');

            try {
                await api.put(`/licitacoes/${id}`, dados);
                ui.showAlert('Licitação atualizada com sucesso!', 'success');
                fecharModal('modalEditarLicitacao');
                self.carregarDetalhe(id);
                self.carregarLicitacoes();
            } catch (error) {
                ui.showAlert(error.message || 'Erro ao atualizar licitação', 'error');
            } finally {
                ui.setButtonLoading(button, false, 'btnEditarText', 'btnEditarSpinner');
            }
        });

        // Form mudar status
        document.getElementById('formMudarStatus')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('statusLicitacaoId').value;
            const status = document.getElementById('selectNovoStatus').value;
            const observacao = document.getElementById('statusObservacao').value;

            try {
                await api.patch(`/licitacoes/${id}/status`, { status, observacao: observacao || null });
                ui.showAlert('Status atualizado com sucesso!', 'success');
                fecharModal('modalMudarStatus');
                self.carregarDetalhe(id);
                self.carregarLicitacoes();
                self.carregarEstatisticas();
            } catch (error) {
                ui.showAlert(error.message || 'Erro ao mudar status', 'error');
            }
        });
    },

    async excluirLicitacao(id) {
        if (!await confirmAction('Tem certeza que deseja excluir esta licitação?', { type: 'danger', confirmText: 'Excluir' })) return;

        try {
            await api.delete(`/licitacoes/${id}`);
            ui.showAlert('Licitação excluída com sucesso!', 'success');
            this.carregarLicitacoes();
            this.carregarEstatisticas();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao excluir licitação', 'error');
        }
    },

    // === DETALHE ===

    async carregarDetalhe(id) {
        document.getElementById('listaLicitacoes').classList.add('hidden');
        document.getElementById('paginacao').classList.add('hidden');
        document.getElementById('statsContainer').classList.add('hidden');
        document.querySelector('.filtros-bar')?.classList.add('hidden');
        document.querySelector('.d-flex.justify-between.align-center.mb-3')?.classList.add('hidden');
        document.getElementById('detalheLicitacao').classList.remove('hidden');

        await ErrorHandler.withErrorHandling(async () => {
            const l = await api.get(`/licitacoes/${id}`);
            this.licitacaoAtual = l;

            document.getElementById('detalheNumero').textContent = `${l.numero} - ${l.orgao}`;

            // Status badge
            const statusLabel = STATUS_LABELS[l.status] || l.status;
            document.getElementById('detalheStatusBadge').innerHTML =
                `<span class="status-badge status-badge-${l.status}">${statusLabel}</span>`;

            // Habilitar/desabilitar botao mudar status
            const transitions = STATUS_TRANSITIONS[l.status] || [];
            const btnStatus = document.getElementById('btnMudarStatus');
            if (btnStatus) {
                btnStatus.disabled = transitions.length === 0;
                btnStatus.title = transitions.length === 0 ? 'Status final - sem transições disponíveis' : '';
            }

            // Tab Dados
            this.renderDados(l);

            // Tab Historico
            this.renderHistorico(l.historico || []);

            // Tab Tags
            this.renderTags(l);

            // Resetar para tab Dados
            this.switchDetalheTab('dados');

            window.history.pushState({}, '', `licitacoes.html?id=${id}`);
        }, 'Erro ao carregar licitação');
    },

    renderDados(l) {
        const formatDate = (d) => d ? new Date(d).toLocaleDateString('pt-BR') : '-';
        const formatCurrency = (v) => v ? `R$ ${Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : '-';

        const fields = [
            { label: 'Número', value: l.numero },
            { label: 'Órgão', value: l.orgao },
            { label: 'Objeto', value: l.objeto, fullWidth: true },
            { label: 'Modalidade', value: l.modalidade },
            { label: 'Fonte', value: l.fonte },
            { label: 'Valor Estimado', value: formatCurrency(l.valor_estimado) },
            { label: 'Valor Homologado', value: formatCurrency(l.valor_homologado) },
            { label: 'Valor Proposta', value: formatCurrency(l.valor_proposta) },
            { label: 'UF', value: l.uf || '-' },
            { label: 'Município', value: l.municipio || '-' },
            { label: 'Esfera', value: l.esfera || '-' },
            { label: 'PNCP', value: l.numero_controle_pncp || '-' },
            { label: 'Data Publicação', value: formatDate(l.data_publicacao) },
            { label: 'Data Abertura', value: formatDate(l.data_abertura) },
            { label: 'Data Encerramento', value: formatDate(l.data_encerramento) },
            { label: 'Data Resultado', value: formatDate(l.data_resultado) },
            { label: 'Decisão GO', value: l.decisao_go === null ? '-' : (l.decisao_go ? 'GO' : 'NO-GO') },
            { label: 'Motivo NO-GO', value: l.motivo_nogo || '-' },
        ];

        if (l.link_edital) {
            fields.push({ label: 'Link Edital', value: `<a href="${Sanitize.escapeHtml(l.link_edital)}" target="_blank" rel="noopener">Abrir</a>`, html: true });
        }
        if (l.observacoes) {
            fields.push({ label: 'Observações', value: l.observacoes, fullWidth: true });
        }

        document.getElementById('detalheDados').innerHTML = fields.map(f => `
            <div class="detalhe-field${f.fullWidth ? ' detalhe-full-width' : ''}">
                <label>${f.label}</label>
                <span>${f.html ? f.value : Sanitize.escapeHtml(String(f.value))}</span>
            </div>
        `).join('');
    },

    renderHistorico(historico) {
        const container = document.getElementById('detalheHistorico');
        if (!historico || historico.length === 0) {
            container.innerHTML = '<p class="text-muted">Nenhum registro de histórico.</p>';
            return;
        }

        container.innerHTML = historico.map(h => {
            const anteriorLabel = h.status_anterior ? STATUS_LABELS[h.status_anterior] || h.status_anterior : 'Novo';
            const novoLabel = STATUS_LABELS[h.status_novo] || h.status_novo;
            const data = new Date(h.created_at).toLocaleString('pt-BR');

            return `
                <div class="historico-item">
                    <div class="historico-item-header">
                        <span class="status-badge status-badge-${h.status_anterior || 'identificada'}">${anteriorLabel}</span>
                        <span>&#8594;</span>
                        <span class="status-badge status-badge-${h.status_novo}">${novoLabel}</span>
                    </div>
                    <div class="historico-item-date">${data}</div>
                    ${h.observacao ? `<div class="historico-item-obs">${Sanitize.escapeHtml(h.observacao)}</div>` : ''}
                </div>
            `;
        }).join('');
    },

    renderTags(l) {
        const container = document.getElementById('detalheTags');
        const tags = l.tags || [];

        if (tags.length === 0) {
            container.innerHTML = '<p class="text-muted">Nenhuma tag associada.</p>';
            return;
        }

        container.innerHTML = `<div class="licitacao-card-tags">${tags.map(t => `
            <span class="tag-chip">
                ${Sanitize.escapeHtml(t.tag)}
                <button class="tag-chip-remove" data-action="remover-tag" data-tag="${Sanitize.escapeHtml(t.tag)}" title="Remover tag">&times;</button>
            </span>
        `).join('')}</div>`;
    },

    switchDetalheTab(tabName) {
        document.querySelectorAll('#detalheTabs .detalhe-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        document.getElementById('tabDados').classList.toggle('active', tabName === 'dados');
        document.getElementById('tabHistorico').classList.toggle('active', tabName === 'historico');
        document.getElementById('tabTags').classList.toggle('active', tabName === 'tags');
    },

    voltarLista() {
        document.getElementById('detalheLicitacao').classList.add('hidden');
        document.getElementById('listaLicitacoes').classList.remove('hidden');
        document.getElementById('paginacao').classList.remove('hidden');
        document.getElementById('statsContainer').classList.remove('hidden');
        document.querySelector('.filtros-bar')?.classList.remove('hidden');
        document.querySelector('.d-flex.justify-between.align-center.mb-3')?.classList.remove('hidden');
        window.history.pushState({}, '', 'licitacoes.html');
        this.licitacaoAtual = null;
        this.carregarLicitacoes();
        this.carregarEstatisticas();
    },

    // === MODAIS ===

    abrirModalNova() {
        document.getElementById('formNovaLicitacao')?.reset();
        document.getElementById('modalNovaLicitacao').classList.add('active');
    },

    abrirModalEditar() {
        const l = this.licitacaoAtual;
        if (!l) return;

        document.getElementById('editarId').value = l.id;
        document.getElementById('editarNumero').value = l.numero || '';
        document.getElementById('editarOrgao').value = l.orgao || '';
        document.getElementById('editarObjeto').value = l.objeto || '';
        document.getElementById('editarModalidade').value = l.modalidade || '';
        document.getElementById('editarValorEstimado').value = l.valor_estimado || '';
        document.getElementById('editarValorHomologado').value = l.valor_homologado || '';
        document.getElementById('editarValorProposta').value = l.valor_proposta || '';
        document.getElementById('editarUF').value = l.uf || '';
        document.getElementById('editarMunicipio').value = l.municipio || '';

        // Datas: converter ISO para datetime-local format
        const toLocal = (iso) => {
            if (!iso) return '';
            const d = new Date(iso);
            return d.toISOString().slice(0, 16);
        };
        document.getElementById('editarDataPublicacao').value = toLocal(l.data_publicacao);
        document.getElementById('editarDataAbertura').value = toLocal(l.data_abertura);
        document.getElementById('editarDataEncerramento').value = toLocal(l.data_encerramento);
        document.getElementById('editarDataResultado').value = toLocal(l.data_resultado);
        document.getElementById('editarLinkEdital').value = l.link_edital || '';
        document.getElementById('editarObservacoes').value = l.observacoes || '';

        document.getElementById('modalEditarLicitacao').classList.add('active');
    },

    abrirModalMudarStatus() {
        const l = this.licitacaoAtual;
        if (!l) return;

        const transitions = STATUS_TRANSITIONS[l.status] || [];
        if (transitions.length === 0) {
            ui.showAlert('Este status não permite transições.', 'warning');
            return;
        }

        document.getElementById('statusLicitacaoId').value = l.id;
        document.getElementById('statusObservacao').value = '';

        const select = document.getElementById('selectNovoStatus');
        select.innerHTML = transitions.map(s =>
            `<option value="${s}">${STATUS_LABELS[s] || s}</option>`
        ).join('');

        document.getElementById('modalMudarStatus').classList.add('active');
    },

    // === TAGS ===

    async adicionarTag() {
        const input = document.getElementById('inputNovaTag');
        const tag = input.value.trim();
        if (!tag || !this.licitacaoAtual) return;

        try {
            await api.post(`/licitacoes/${this.licitacaoAtual.id}/tags`, { tag });
            input.value = '';
            this.carregarDetalhe(this.licitacaoAtual.id);
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao adicionar tag', 'error');
        }
    },

    async removerTag(tag) {
        if (!this.licitacaoAtual) return;

        try {
            await api.delete(`/licitacoes/${this.licitacaoAtual.id}/tags/${encodeURIComponent(tag)}`);
            this.carregarDetalhe(this.licitacaoAtual.id);
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao remover tag', 'error');
        }
    },
};

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', async () => {
    await loadAuthConfig();
    LicitacoesModule.init();

    // Event delegation para acoes dinamicas
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;

        switch (action) {
            case 'ver-detalhe':
                LicitacoesModule.carregarDetalhe(btn.dataset.id);
                break;
            case 'excluir':
                LicitacoesModule.excluirLicitacao(btn.dataset.id);
                break;
            case 'pagina':
                LicitacoesModule.carregarLicitacoes(parseInt(btn.dataset.page));
                break;
            case 'remover-tag':
                LicitacoesModule.removerTag(btn.dataset.tag);
                break;
        }
    });

    // Botoes de pagina
    document.getElementById('btnNovaLicitacao')?.addEventListener('click', () =>
        LicitacoesModule.abrirModalNova());

    document.getElementById('btnVoltarLista')?.addEventListener('click', () =>
        LicitacoesModule.voltarLista());

    document.getElementById('btnEditarLicitacao')?.addEventListener('click', () =>
        LicitacoesModule.abrirModalEditar());

    document.getElementById('btnMudarStatus')?.addEventListener('click', () =>
        LicitacoesModule.abrirModalMudarStatus());

    document.getElementById('btnAdicionarTag')?.addEventListener('click', () =>
        LicitacoesModule.adicionarTag());

    // Enter no input de tag
    document.getElementById('inputNovaTag')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            LicitacoesModule.adicionarTag();
        }
    });

    // Tabs de detalhe
    document.querySelectorAll('#detalheTabs .detalhe-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            LicitacoesModule.switchDetalheTab(tab.dataset.tab);
        });
    });
});
