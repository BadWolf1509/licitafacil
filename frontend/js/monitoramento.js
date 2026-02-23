// LicitaFacil - Modulo de Monitoramento PNCP
// Gerencia monitores, resultados e busca direta no Portal Nacional de Contratacoes Publicas

const PncpModule = {
    // Estado
    filtros: { ativo: null, busca: '' },
    filtrosResultado: { monitoramento_id: '', status: '', uf: '', busca: '' },
    paginaMonitores: 1,
    paginaResultados: 1,
    monitorEditId: null,
    resultadoImportarId: null,
    state: { buscaResultados: [] },

    // === INICIALIZACAO ===

    init() {
        this.setupEventDelegation();
        this.setupFiltros();
        this.carregarMonitores();
        this.carregarSelectMonitoramentos();
    },

    // === EVENT DELEGATION ===

    setupEventDelegation() {
        const self = this;

        document.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;
            const action = btn.dataset.action;

            switch (action) {
                // Tabs
                case 'switchTab':
                    self.switchTab(btn.dataset.tab);
                    break;

                // Monitores
                case 'novoMonitor':
                    self.novoMonitor();
                    break;
                case 'salvarMonitor':
                    self.salvarMonitor();
                    break;
                case 'editarMonitor':
                    self.editarMonitor(btn.dataset.id);
                    break;
                case 'toggleMonitor':
                    self.toggleMonitor(btn.dataset.id);
                    break;
                case 'excluirMonitor':
                    self.excluirMonitor(btn.dataset.id);
                    break;
                case 'sincronizar':
                    self.sincronizar();
                    break;

                // Resultados
                case 'marcarInteressante':
                    self.marcarStatus(btn.dataset.id, 'interessante');
                    break;
                case 'marcarDescartado':
                    self.marcarStatus(btn.dataset.id, 'descartado');
                    break;
                case 'abrirImportar':
                    self.abrirImportar(btn.dataset.id);
                    break;
                case 'confirmarImportar':
                    self.confirmarImportar();
                    break;

                // Paginacao
                case 'paginaMonitores':
                    self.carregarMonitores(parseInt(btn.dataset.page));
                    break;
                case 'paginaResultados':
                    self.carregarResultados(parseInt(btn.dataset.page));
                    break;

                // Busca direta
                case 'buscarDireta':
                    self.buscarDireta();
                    break;
                case 'importarBuscaDireta':
                    self.importarBuscaDireta(parseInt(btn.dataset.index));
                    break;
            }
        });
    },

    // === TABS ===

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.monitor-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab content
        document.getElementById('tabMonitores').classList.toggle('active', tabName === 'monitores');
        document.getElementById('tabResultados').classList.toggle('active', tabName === 'resultados');
        document.getElementById('tabBusca').classList.toggle('active', tabName === 'busca');

        // Load data on tab switch
        if (tabName === 'monitores') {
            this.carregarMonitores();
        } else if (tabName === 'resultados') {
            this.carregarResultados();
        }
    },

    // === FILTROS ===

    setupFiltros() {
        const self = this;
        const debouncedLoad = ui.debounce(() => self.carregarResultados(1), CONFIG.TIMEOUTS.DEBOUNCE_INPUT);

        document.getElementById('filtroMonitoramento')?.addEventListener('change', function() {
            self.filtrosResultado.monitoramento_id = this.value;
            self.carregarResultados(1);
        });
        document.getElementById('filtroStatusResultado')?.addEventListener('change', function() {
            self.filtrosResultado.status = this.value;
            self.carregarResultados(1);
        });
        document.getElementById('filtroUFResultado')?.addEventListener('change', function() {
            self.filtrosResultado.uf = this.value;
            self.carregarResultados(1);
        });
        document.getElementById('filtroBuscaResultado')?.addEventListener('input', function() {
            self.filtrosResultado.busca = this.value;
            debouncedLoad();
        });
    },

    // === MONITORES - CRUD ===

    async carregarMonitores(pagina) {
        if (pagina) this.paginaMonitores = pagina;

        await ErrorHandler.withErrorHandling(async () => {
            const params = new URLSearchParams({
                page: this.paginaMonitores,
                page_size: 12,
            });
            if (this.filtros.ativo !== null) params.set('ativo', this.filtros.ativo);
            if (this.filtros.busca) params.set('busca', this.filtros.busca);

            const response = await api.get(`/pncp/monitoramentos?${params}`);
            this.renderMonitores(response);
            this.renderPaginacao('monitoresPaginacao', this.paginaMonitores, response.total_pages || 1, 'paginaMonitores');
        }, 'Erro ao carregar monitores', { container: 'monitoresGrid' });
    },

    renderMonitores(response) {
        const container = document.getElementById('monitoresGrid');
        const monitores = response.items || [];

        if (monitores.length === 0) {
            container.innerHTML = `
                <div class="card empty-state" style="grid-column: 1 / -1;">
                    <h3>Nenhum monitor encontrado</h3>
                    <p class="text-muted">Crie seu primeiro monitor clicando em "+ Novo Monitor"</p>
                </div>
            `;
            return;
        }

        container.innerHTML = monitores.map(m => {
            const palavras = (m.palavras_chave || []).map(p =>
                `<span class="keyword-badge">${Sanitize.escapeHtml(p)}</span>`
            ).join('');

            const ufsHtml = (m.ufs || []).map(u =>
                `<span class="uf-badge">${Sanitize.escapeHtml(u)}</span>`
            ).join('');

            const statusClass = m.ativo ? 'status-ativo' : 'status-inativo';
            const statusLabel = m.ativo ? 'Ativo' : 'Inativo';
            const toggleLabel = m.ativo ? 'Desativar' : 'Ativar';
            const toggleBtnClass = m.ativo ? 'btn-outline' : 'btn-success';

            const valorMin = m.valor_minimo ? this.formatarValor(m.valor_minimo) : '';
            const valorMax = m.valor_maximo ? this.formatarValor(m.valor_maximo) : '';
            const valorRange = (valorMin || valorMax)
                ? `<div class="monitor-valor-range">${valorMin ? 'Min: ' + valorMin : ''}${valorMin && valorMax ? ' | ' : ''}${valorMax ? 'Max: ' + valorMax : ''}</div>`
                : '';

            return `
                <div class="card monitor-card">
                    <div class="monitor-card-header">
                        <h3 class="monitor-card-title">${Sanitize.escapeHtml(m.nome)}</h3>
                        <span class="monitor-status ${statusClass}">${statusLabel}</span>
                    </div>
                    <div class="monitor-card-body">
                        <div class="monitor-keywords">${palavras || '<span class="text-muted">Sem palavras-chave</span>'}</div>
                        ${ufsHtml ? `<div class="monitor-ufs">${ufsHtml}</div>` : ''}
                        ${valorRange}
                    </div>
                    <div class="monitor-card-actions">
                        <button class="btn btn-outline btn-sm" data-action="editarMonitor" data-id="${m.id}">Editar</button>
                        <button class="btn ${toggleBtnClass} btn-sm" data-action="toggleMonitor" data-id="${m.id}">${toggleLabel}</button>
                        <button class="btn btn-danger btn-sm" data-action="excluirMonitor" data-id="${m.id}">Excluir</button>
                    </div>
                </div>
            `;
        }).join('');
    },

    novoMonitor() {
        this.monitorEditId = null;
        document.getElementById('modalMonitorTitulo').textContent = 'Novo Monitor';
        document.getElementById('monitorId').value = '';
        document.getElementById('monitorNome').value = '';
        document.getElementById('monitorPalavrasChave').value = '';
        document.getElementById('monitorValorMinimo').value = '';
        document.getElementById('monitorValorMaximo').value = '';
        document.getElementById('monitorAtivo').checked = true;

        // Limpar checkboxes de UF
        document.querySelectorAll('#monitorUFs input[type="checkbox"]').forEach(cb => {
            cb.checked = false;
        });

        abrirModal('modalMonitor');
    },

    async editarMonitor(id) {
        try {
            const monitor = await api.get(`/pncp/monitoramentos/${id}`);
            this.monitorEditId = id;

            document.getElementById('modalMonitorTitulo').textContent = 'Editar Monitor';
            document.getElementById('monitorId').value = id;
            document.getElementById('monitorNome').value = monitor.nome || '';
            document.getElementById('monitorPalavrasChave').value = (monitor.palavras_chave || []).join(', ');
            document.getElementById('monitorValorMinimo').value = monitor.valor_minimo || '';
            document.getElementById('monitorValorMaximo').value = monitor.valor_maximo || '';
            document.getElementById('monitorAtivo').checked = monitor.ativo !== false;

            // Marcar UFs
            const ufs = monitor.ufs || [];
            document.querySelectorAll('#monitorUFs input[type="checkbox"]').forEach(cb => {
                cb.checked = ufs.includes(cb.value);
            });

            abrirModal('modalMonitor');
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao carregar monitor', 'error');
        }
    },

    async salvarMonitor() {
        const nome = document.getElementById('monitorNome').value.trim();
        const palavrasChaveStr = document.getElementById('monitorPalavrasChave').value.trim();
        const valorMinimo = document.getElementById('monitorValorMinimo').value;
        const valorMaximo = document.getElementById('monitorValorMaximo').value;
        const ativo = document.getElementById('monitorAtivo').checked;

        if (!nome) {
            ui.showAlert('Informe o nome do monitor', 'warning');
            return;
        }
        if (!palavrasChaveStr) {
            ui.showAlert('Informe ao menos uma palavra-chave', 'warning');
            return;
        }

        const palavras_chave = palavrasChaveStr.split(',').map(p => p.trim()).filter(p => p.length > 0);

        // Coletar UFs selecionadas
        const ufs = [];
        document.querySelectorAll('#monitorUFs input[type="checkbox"]:checked').forEach(cb => {
            ufs.push(cb.value);
        });

        const dados = {
            nome,
            palavras_chave,
            ufs,
            ativo,
        };
        if (valorMinimo) dados.valor_minimo = parseFloat(valorMinimo);
        if (valorMaximo) dados.valor_maximo = parseFloat(valorMaximo);

        const button = document.querySelector('[data-action="salvarMonitor"]');
        const textEl = document.getElementById('btnSalvarMonitorText');
        const spinnerEl = document.getElementById('btnSalvarMonitorSpinner');

        if (button) button.disabled = true;
        if (textEl) textEl.classList.add('hidden');
        if (spinnerEl) spinnerEl.classList.remove('hidden');

        try {
            if (this.monitorEditId) {
                await api.put(`/pncp/monitoramentos/${this.monitorEditId}`, dados);
                ui.showAlert('Monitor atualizado com sucesso!', 'success');
            } else {
                await api.post('/pncp/monitoramentos', dados);
                ui.showAlert('Monitor criado com sucesso!', 'success');
            }
            fecharModal('modalMonitor');
            this.carregarMonitores();
            this.carregarSelectMonitoramentos();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao salvar monitor', 'error');
        } finally {
            if (button) button.disabled = false;
            if (textEl) textEl.classList.remove('hidden');
            if (spinnerEl) spinnerEl.classList.add('hidden');
        }
    },

    async excluirMonitor(id) {
        if (!await confirmAction('Tem certeza que deseja excluir este monitor? Todos os resultados associados também serão removidos.', {
            type: 'danger',
            confirmText: 'Excluir',
            title: 'Excluir Monitor'
        })) return;

        try {
            await api.delete(`/pncp/monitoramentos/${id}`);
            ui.showAlert('Monitor excluído com sucesso!', 'success');
            this.carregarMonitores();
            this.carregarSelectMonitoramentos();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao excluir monitor', 'error');
        }
    },

    async toggleMonitor(id) {
        try {
            await api.patch(`/pncp/monitoramentos/${id}/toggle`, {});
            this.carregarMonitores();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao alterar status do monitor', 'error');
        }
    },

    // === RESULTADOS ===

    async carregarSelectMonitoramentos() {
        try {
            const response = await api.get('/pncp/monitoramentos?page_size=100');
            const select = document.getElementById('filtroMonitoramento');
            if (!select) return;

            const currentValue = select.value;
            select.innerHTML = '<option value="">Todos</option>';
            (response.items || []).forEach(m => {
                const option = document.createElement('option');
                option.value = m.id;
                option.textContent = m.nome;
                select.appendChild(option);
            });
            select.value = currentValue;
        } catch (error) {
            console.warn('Erro ao carregar lista de monitoramentos:', error);
        }
    },

    async carregarResultados(pagina) {
        if (pagina) this.paginaResultados = pagina;

        await ErrorHandler.withErrorHandling(async () => {
            const params = new URLSearchParams({
                page: this.paginaResultados,
                page_size: 20,
            });
            if (this.filtrosResultado.monitoramento_id) params.set('monitoramento_id', this.filtrosResultado.monitoramento_id);
            if (this.filtrosResultado.status) params.set('status', this.filtrosResultado.status);
            if (this.filtrosResultado.uf) params.set('uf', this.filtrosResultado.uf);
            if (this.filtrosResultado.busca) params.set('busca', this.filtrosResultado.busca);

            const response = await api.get(`/pncp/resultados?${params}`);
            this.renderResultados(response);
            this.renderPaginacao('resultadosPaginacao', this.paginaResultados, response.total_pages || 1, 'paginaResultados');
        }, 'Erro ao carregar resultados', { container: 'resultadosTabela' });
    },

    renderResultados(response) {
        const container = document.getElementById('resultadosTabela');
        const resultados = response.items || [];

        if (resultados.length === 0) {
            container.innerHTML = `
                <div class="card empty-state">
                    <h3>Nenhum resultado encontrado</h3>
                    <p class="text-muted">Ajuste os filtros ou aguarde a próxima sincronização</p>
                </div>
            `;
            return;
        }

        let html = `
            <div class="table-container">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Número</th>
                            <th>Órgão</th>
                            <th>Objeto</th>
                            <th>UF</th>
                            <th>Valor</th>
                            <th>Status</th>
                            <th>Ações</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        html += resultados.map(r => {
            const objeto = r.objeto || '';
            const objetoTruncado = objeto.length > 100 ? objeto.substring(0, 100) + '...' : objeto;
            const valorStr = r.valor ? this.formatarValor(r.valor) : '-';

            return `
                <tr>
                    <td>${Sanitize.escapeHtml(r.numero_controle || '-')}</td>
                    <td>${Sanitize.escapeHtml(r.orgao || '-')}</td>
                    <td class="resultado-objeto" title="${Sanitize.escapeHtml(objeto)}">${Sanitize.escapeHtml(objetoTruncado)}</td>
                    <td>${Sanitize.escapeHtml(r.uf || '-')}</td>
                    <td class="valor-currency">${valorStr}</td>
                    <td>${this.getStatusBadge(r.status)}</td>
                    <td class="resultado-acoes">
                        ${r.status !== 'interessante' ? `<button class="btn btn-success btn-sm" data-action="marcarInteressante" data-id="${r.id}" title="Marcar como interessante">Interessante</button>` : ''}
                        ${r.status !== 'descartado' ? `<button class="btn btn-outline btn-sm" data-action="marcarDescartado" data-id="${r.id}" title="Descartar">Descartar</button>` : ''}
                        ${r.status !== 'importado' ? `<button class="btn btn-primary btn-sm" data-action="abrirImportar" data-id="${r.id}" title="Importar como licitação">Importar</button>` : ''}
                    </td>
                </tr>
            `;
        }).join('');

        html += '</tbody></table></div>';
        container.innerHTML = html;
    },

    async marcarStatus(id, status) {
        try {
            await api.patch(`/pncp/resultados/${id}/status`, { status });
            ui.showAlert(`Resultado marcado como "${status}"`, 'success');
            this.carregarResultados();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao atualizar status', 'error');
        }
    },

    abrirImportar(id) {
        this.resultadoImportarId = id;
        document.getElementById('importarObservacoes').value = '';
        document.getElementById('importarResumo').innerHTML = `
            <p class="text-muted">O resultado selecionado será importado como uma nova licitação no sistema.</p>
        `;
        abrirModal('modalImportar');
    },

    async confirmarImportar() {
        if (!this.resultadoImportarId) return;

        const observacoes = document.getElementById('importarObservacoes').value.trim();

        const button = document.querySelector('[data-action="confirmarImportar"]');
        const textEl = document.getElementById('btnImportarText');
        const spinnerEl = document.getElementById('btnImportarSpinner');

        if (button) button.disabled = true;
        if (textEl) textEl.classList.add('hidden');
        if (spinnerEl) spinnerEl.classList.remove('hidden');

        try {
            await api.post(`/pncp/resultados/${this.resultadoImportarId}/importar`, {
                observacoes: observacoes || null
            });
            ui.showAlert('Resultado importado como licitação com sucesso!', 'success');
            fecharModal('modalImportar');
            this.resultadoImportarId = null;
            this.carregarResultados();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao importar resultado', 'error');
        } finally {
            if (button) button.disabled = false;
            if (textEl) textEl.classList.remove('hidden');
            if (spinnerEl) spinnerEl.classList.add('hidden');
        }
    },

    // === BUSCA DIRETA ===

    async buscarDireta() {
        const dataInicial = document.getElementById('buscaDataInicial').value;
        const dataFinal = document.getElementById('buscaDataFinal').value;
        const uf = document.getElementById('buscaUF').value;
        const codigoModalidade = document.getElementById('buscaModalidade').value;

        if (!dataInicial || !dataFinal) {
            ui.showAlert('Informe a data inicial e a data final', 'warning');
            return;
        }

        if (!codigoModalidade) {
            ui.showAlert('Selecione uma modalidade de contratação', 'warning');
            return;
        }

        await ErrorHandler.withErrorHandling(async () => {
            const params = new URLSearchParams({
                data_inicial: dataInicial.replace(/-/g, ''),
                data_final: dataFinal.replace(/-/g, ''),
            });
            if (uf) params.set('uf', uf);
            if (codigoModalidade) params.set('codigo_modalidade', codigoModalidade);

            const response = await api.get(`/pncp/busca?${params}`);
            this.renderBuscaResultados(response);
        }, 'Erro ao buscar no PNCP', { container: 'buscaResultados' });
    },

    renderBuscaResultados(response) {
        const container = document.getElementById('buscaResultados');
        const resultados = response.items || response.data || response || [];

        if (!Array.isArray(resultados) || resultados.length === 0) {
            container.innerHTML = `
                <div class="card empty-state">
                    <h3>Nenhum resultado encontrado</h3>
                    <p class="text-muted">Tente alterar os filtros de busca</p>
                </div>
            `;
            return;
        }

        let html = `
            <div class="card">
                <h3 class="mb-2">${resultados.length} resultado(s) encontrado(s)</h3>
                <div class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Processo</th>
                                <th>Órgão</th>
                                <th>Objeto</th>
                                <th>UF</th>
                                <th>Valor</th>
                                <th>Abertura</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        html += resultados.map((r, idx) => {
            const objeto = r.objetoCompra || r.objeto || '';
            const objetoTruncado = objeto.length > 120 ? objeto.substring(0, 120) + '...' : objeto;
            const unidade = r.unidadeOrgao || {};
            const orgao = r.orgaoEntidade || {};
            const ufVal = unidade.ufSigla || r.uf || '-';
            const valorStr = r.valorTotalEstimado ? this.formatarValor(r.valorTotalEstimado) : '-';
            const dataStr = r.dataAberturaProposta ? this.formatarData(r.dataAberturaProposta) : '-';
            const link = r.linkSistemaOrigem || '';
            const processo = r.processo || '-';

            return `
                <tr>
                    <td>${Sanitize.escapeHtml(processo)}</td>
                    <td>${Sanitize.escapeHtml(orgao.razaoSocial || '-')}</td>
                    <td class="resultado-objeto" title="${Sanitize.escapeHtml(objeto)}">${Sanitize.escapeHtml(objetoTruncado)}</td>
                    <td>${Sanitize.escapeHtml(ufVal)}</td>
                    <td class="valor-currency">${valorStr}</td>
                    <td>${dataStr}</td>
                    <td class="resultado-acoes">
                        ${link ? `<a href="${Sanitize.escapeHtml(link)}" target="_blank" rel="noopener" class="btn btn-outline btn-sm">Ver PNCP</a>` : ''}
                        <button class="btn btn-primary btn-sm" data-action="importarBuscaDireta" data-index="${idx}" title="Importar como licitação">Importar</button>
                    </td>
                </tr>
            `;
        }).join('');

        // Guardar resultados para importação
        this.state.buscaResultados = resultados;

        html += '</tbody></table></div></div>';
        container.innerHTML = html;
    },

    // === IMPORTAR DA BUSCA DIRETA ===

    async importarBuscaDireta(index) {
        const item = this.state.buscaResultados[index];
        if (!item) {
            ui.showAlert('Item não encontrado', 'error');
            return;
        }

        const orgao = item.orgaoEntidade?.razaoSocial || 'Órgão não informado';
        const objeto = (item.objetoCompra || '').substring(0, 100);
        if (!await confirmAction(
            `Importar como licitação?\n\nÓrgão: ${orgao}\nObjeto: ${objeto}...`,
            { title: 'Importar Licitação', confirmText: 'Importar', type: 'info' }
        )) return;

        try {
            const result = await api.post('/pncp/busca/importar', item);
            ui.showAlert(result.message || 'Licitação importada com sucesso!', 'success');
            // Desabilitar botão do item importado
            const btn = document.querySelector(`[data-action="importarBuscaDireta"][data-index="${index}"]`);
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Importado';
                btn.classList.remove('btn-primary');
                btn.classList.add('btn-outline');
            }
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao importar licitação', 'error');
        }
    },

    // === SINCRONIZACAO ===

    async sincronizar() {
        if (!await confirmAction('Deseja sincronizar todos os monitores ativos agora? Isso pode levar alguns instantes.', {
            title: 'Sincronizar Monitores',
            confirmText: 'Sincronizar',
            type: 'warning'
        })) return;

        try {
            ui.showAlert('Iniciando sincronização...', 'info');
            const result = await api.post('/pncp/sincronizar', {});
            const msg = result.message || `Sincronização concluída. ${result.novos || 0} novo(s) resultado(s) encontrado(s).`;
            ui.showAlert(msg, 'success');
            this.carregarMonitores();
            this.carregarResultados();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao sincronizar', 'error');
        }
    },

    // === PAGINACAO ===

    renderPaginacao(containerId, paginaAtual, totalPages, actionName) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        let html = '';
        if (paginaAtual > 1) {
            html += `<button class="btn btn-outline btn-sm" data-action="${actionName}" data-page="${paginaAtual - 1}">Anterior</button>`;
        }

        // Show max 7 page buttons
        let startPage = Math.max(1, paginaAtual - 3);
        let endPage = Math.min(totalPages, startPage + 6);
        if (endPage - startPage < 6) {
            startPage = Math.max(1, endPage - 6);
        }

        for (let i = startPage; i <= endPage; i++) {
            const active = i === paginaAtual ? 'btn-primary' : 'btn-outline';
            html += `<button class="btn ${active} btn-sm" data-action="${actionName}" data-page="${i}">${i}</button>`;
        }

        if (paginaAtual < totalPages) {
            html += `<button class="btn btn-outline btn-sm" data-action="${actionName}" data-page="${paginaAtual + 1}">Próximo</button>`;
        }

        container.innerHTML = html;
    },

    // === HELPERS ===

    formatarValor(valor) {
        if (valor === null || valor === undefined) return '-';
        const num = Number(valor);
        if (!Number.isFinite(num)) return '-';
        return `R$ ${num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },

    formatarData(dateStr) {
        if (!dateStr) return '-';
        const data = new Date(dateStr);
        if (isNaN(data.getTime())) return '-';
        return data.toLocaleDateString('pt-BR');
    },

    getStatusBadge(status) {
        const labels = {
            novo: 'Novo',
            interessante: 'Interessante',
            descartado: 'Descartado',
            importado: 'Importado',
        };
        const label = labels[status] || status || 'Novo';
        const safeStatus = Sanitize.escapeHtml(status || 'novo');
        const safeLabel = Sanitize.escapeHtml(label);
        return `<span class="resultado-status resultado-status-${safeStatus}">${safeLabel}</span>`;
    },
};

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', async () => {
    await loadAuthConfig();
    PncpModule.init();
});
