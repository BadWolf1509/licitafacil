// LicitaFacil - Modulo de Analises
// Gerencia CRUD, upload e processamento de analises de licitacao

const AnalisesModule = {
    // Estado
    arquivoSelecionado: null,
    exigenciaCounter: 0,

    // Inicializacao
    init() {
        this.carregarAnalises();
        this.setupUploadAnalise();
        this.setupFormNovaAnalise();
        this.setupFormAnaliseManual();

        // Verificar se ha ID na URL
        const params = new URLSearchParams(window.location.search);
        const id = params.get('id');
        if (id) {
            this.carregarDetalheAnalise(id);
        }
    },

    // === LISTAGEM E DETALHES ===

    async carregarAnalises() {
        await ErrorHandler.withErrorHandling(async () => {
            const response = await api.get('/analises/');
            const analises = response.items || [];
            const container = document.getElementById('listaAnalises');

            if (analises.length === 0) {
                container.innerHTML = `
                    <div class="card empty-state">
                        <div class="empty-state-icon">&#128269;</div>
                        <h3>Nenhuma análise realizada</h3>
                        <p class="text-muted">Faça sua primeira análise de licitação</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = analises.map(a => {
                const hasResults = a.resultado_json && a.resultado_json.length > 0;
                const hasExigencias = a.exigencias_json && a.exigencias_json.length > 0;
                let status;
                if (hasResults) {
                    status = a.resultado_json.every(r => r.status === 'atende') ? 'atende' :
                             a.resultado_json.some(r => r.status === 'atende') ? 'parcial' : 'nao-atende';
                } else if (a.arquivo_path) {
                    status = 'pendente';
                } else if (hasExigencias) {
                    status = 'manual-falhou';
                } else {
                    status = 'manual-vazio';
                }

                const statusIcon = {
                    'atende': '&#9989;', 'parcial': '&#9888;', 'nao-atende': '&#10060;',
                    'pendente': '&#9203;', 'manual-falhou': '&#10060;', 'manual-vazio': '&#9997;'
                }[status];

                const statusText = {
                    'atende': 'Atende todos os requisitos', 'parcial': 'Atende parcialmente',
                    'nao-atende': 'Não atende', 'pendente': 'Aguardando processamento',
                    'manual-falhou': 'Análise manual falhou', 'manual-vazio': 'Análise manual vazia'
                }[status];

                const badgeClass = {
                    'atende': 'success', 'parcial': 'warning', 'nao-atende': 'error',
                    'pendente': 'info', 'manual-falhou': 'error', 'manual-vazio': 'secondary'
                }[status];

                return `
                    <div class="card">
                        <div class="d-flex justify-between align-center">
                            <div>
                                <h3>${Sanitize.escapeHtml(a.nome_licitacao)}</h3>
                                <p class="text-muted">${formatarData(a.created_at)}</p>
                                <span class="badge badge-${badgeClass}">
                                    <span role="img" aria-hidden="true">${statusIcon}</span> ${statusText}
                                </span>
                            </div>
                            <div class="d-flex gap-1">
                                <button class="btn btn-primary btn-sm" data-action="ver-detalhes" data-id="${a.id}">Ver Detalhes</button>
                                ${!hasResults && a.arquivo_path ? `<button class="btn btn-outline btn-sm" data-action="processar" data-id="${a.id}">Processar</button>` : ''}
                                ${!a.arquivo_path && hasExigencias ? `<button class="btn btn-outline btn-sm" data-action="processar" data-id="${a.id}">Reprocessar</button>` : ''}
                                <button class="btn btn-danger btn-sm" data-action="excluir" data-id="${a.id}">Excluir</button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }, 'Erro ao carregar análises', { container: 'listaAnalises' });
    },

    async carregarDetalheAnalise(id) {
        document.getElementById('listaAnalises').classList.add('hidden');
        document.getElementById('detalheAnalise').classList.remove('hidden');

        await ErrorHandler.withErrorHandling(async () => {
            const analise = await api.get(`/analises/${id}`);
            document.getElementById('analiseNome').textContent = analise.nome_licitacao;

            const container = document.getElementById('resultadoAnalise');

            if (!analise.resultado_json || analise.resultado_json.length === 0) {
                const hasExigencias = analise.exigencias_json && analise.exigencias_json.length > 0;

                if (analise.arquivo_path) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <p>Esta análise ainda não foi processada.</p>
                            <button class="btn btn-primary mt-2" data-action="processar" data-id="${id}">Processar Agora</button>
                        </div>
                    `;
                } else if (hasExigencias) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="badge badge-error mb-2">&#10060; Análise falhou</div>
                            <p>Esta análise manual não conseguiu encontrar correspondências.</p>
                            <p class="text-muted"><strong>Possíveis causas:</strong></p>
                            <ul class="text-muted text-left">
                                <li>Você ainda não cadastrou atestados</li>
                                <li>Seus atestados não possuem serviços compatíveis</li>
                                <li>Erro interno no processamento</li>
                            </ul>
                            <button class="btn btn-primary mt-2" data-action="processar" data-id="${id}">Reprocessar</button>
                        </div>
                    `;
                } else {
                    container.innerHTML = `
                        <div class="empty-state">
                            <p>Esta análise manual está vazia.</p>
                            <p class="text-muted">Crie uma nova analise com as exigencias desejadas.</p>
                        </div>
                    `;
                }
                return;
            }

            container.innerHTML = analise.resultado_json.map(r => {
                const statusIcon = r.status === 'atende' ? '&#9989;' : r.status === 'parcial' ? '&#9888;' : '&#10060;';
                const statusClass = r.status === 'atende' ? 'success' : r.status === 'parcial' ? 'warning' : 'error';
                const exigenciaDescricao = r.exigencia?.descricao || 'Exigência sem descrição';
                const exigenciaQuantidade = r.exigencia?.quantidade_minima;
                const exigenciaUnidade = r.exigencia?.unidade || '-';

                return `
                    <div class="card resultado-card">
                        <div class="resultado-header">
                            <div>
                                <h3>${exigenciaDescricao}</h3>
                                <p class="text-muted">
                                    Mínimo exigido: ${formatarNumero(exigenciaQuantidade)} ${exigenciaUnidade}
                                </p>
                            </div>
                            <div class="resultado-status status-${statusClass}">
                                <span class="status-icon">${statusIcon}</span>
                                <span>${r.percentual_total.toFixed(1)}%</span>
                            </div>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill ${r.status}" style="width: ${Math.min(r.percentual_total, 100)}%"></div>
                        </div>
                        ${r.atestados_recomendados.length > 0 ? `
                            <div class="atestado-lista mt-2">
                                <strong>Atestados recomendados:</strong>
                                ${r.atestados_recomendados.map(at => `
                                    <div class="atestado-item">
                                        <span>${at.descricao_servico}</span>
                                        <span>${formatarNumero(at.quantidade)} ${at.unidade || '-'} (${at.percentual_cobertura.toFixed(1)}%)</span>
                                    </div>
                                    ${(at.itens && at.itens.length) ? `
                                        <details class="atestado-itens">
                                            <summary>Itens usados (${at.itens.length})</summary>
                                            ${at.itens.map(item => `
                                                <div class="atestado-item-detail">
                                                    <span>${item.item ? item.item + ' - ' : ''}${item.descricao || '-'}</span>
                                                    <span>${formatarNumero(item.quantidade)} ${item.unidade || '-'}</span>
                                                </div>
                                            `).join('')}
                                        </details>
                                    ` : ''}
                                `).join('')}
                                <div class="atestado-item" style="font-weight: bold;">
                                    <span>Total</span>
                                    <span>${formatarNumero(r.soma_quantidades)} ${exigenciaUnidade}</span>
                                </div>
                            </div>
                        ` : '<p class="text-muted mt-2">Nenhum atestado compatível encontrado.</p>'}
                    </div>
                `;
            }).join('');
        }, 'Erro ao carregar análise', { container: 'resultadoAnalise' });
    },

    voltarLista() {
        document.getElementById('detalheAnalise').classList.add('hidden');
        document.getElementById('listaAnalises').classList.remove('hidden');
        window.history.pushState({}, '', 'analises.html');
        this.carregarAnalises();
    },

    // === UPLOAD E FORMULARIOS ===

    setupUploadAnalise() {
        const zone = document.getElementById('uploadZoneAnalise');
        const input = document.getElementById('fileInputAnalise');
        const self = this;

        zone.addEventListener('click', () => input.click());

        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type === 'application/pdf') {
                self.arquivoSelecionado = file;
                document.getElementById('nomeArquivo').textContent = `Arquivo: ${file.name}`;
            }
        });

        input.addEventListener('change', () => {
            if (input.files[0]) {
                self.arquivoSelecionado = input.files[0];
                document.getElementById('nomeArquivo').textContent = `Arquivo: ${self.arquivoSelecionado.name}`;
            }
        });
    },

    setupFormNovaAnalise() {
        const self = this;
        document.getElementById('formNovaAnalise').addEventListener('submit', async (e) => {
            e.preventDefault();

            const nomeLicitacao = document.getElementById('nomeLicitacao').value;
            if (!self.arquivoSelecionado) {
                ui.showAlert('Selecione o PDF do edital', 'error');
                return;
            }

            const button = e.target.querySelector('button[type="submit"]');
            ui.setButtonLoading(button, true, 'btnAnaliseText', 'btnAnaliseSpinner');

            try {
                const formData = new FormData();
                formData.append('nome_licitacao', nomeLicitacao);
                formData.append('file', self.arquivoSelecionado);

                const result = await api.upload('/analises/?nome_licitacao=' + encodeURIComponent(nomeLicitacao), formData);

                ui.showAlert('Análise criada com sucesso!', 'success');
                fecharModal('modalNovaAnalise');
                self.arquivoSelecionado = null;
                document.getElementById('formNovaAnalise').reset();
                document.getElementById('nomeArquivo').textContent = '';
                self.carregarAnalises();

                // Processar automaticamente
                if (result.id) {
                    self.processarAnalise(result.id);
                }

            } catch (error) {
                ui.showAlert(error.message || 'Erro ao criar análise', 'error');
            } finally {
                ui.setButtonLoading(button, false, 'btnAnaliseText', 'btnAnaliseSpinner');
            }
        });
    },

    abrirModalNovaAnalise() {
        this.arquivoSelecionado = null;
        this.exigenciaCounter = 0;
        document.getElementById('formNovaAnalise').reset();
        document.getElementById('formAnaliseManual').reset();
        document.getElementById('nomeArquivo').textContent = '';
        document.getElementById('listaExigencias').innerHTML = '';

        // Resetar para tab de upload
        this.switchAnaliseTab('upload');

        // Adicionar uma exigencia inicial
        this.adicionarExigencia();

        document.getElementById('modalNovaAnalise').classList.add('active');
    },

    // === TABS ===

    switchAnaliseTab(tabName) {
        // Atualizar botoes de tab
        document.querySelectorAll('#modalAnaliseTabs .modal-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        // Atualizar conteudos
        document.getElementById('tabAnaliseUpload').classList.toggle('active', tabName === 'upload');
        document.getElementById('tabAnaliseManual').classList.toggle('active', tabName === 'manual');
    },

    // === EXIGENCIAS ===

    adicionarExigencia() {
        this.exigenciaCounter++;
        const container = document.getElementById('listaExigencias');
        const counter = this.exigenciaCounter;

        const exigenciaHtml = `
            <div class="exigencia-item" id="exigencia-${counter}">
                <div class="exigencia-item-header">
                    <span class="exigencia-item-numero">Exigência ${counter}</span>
                    <button type="button" class="exigencia-item-remove" data-action="remover-exigencia" data-id="${counter}" title="Remover">
                        &times;
                    </button>
                </div>
                <div class="form-group">
                    <label class="form-label">Descrição da exigência *</label>
                    <input type="text" class="form-input" name="exigencia_descricao_${counter}" required
                        placeholder="Ex: Execução de pavimentação asfáltica">
                </div>
                <div class="exigencia-row">
                    <div class="form-group">
                        <label class="form-label">Quantidade mínima *</label>
                        <input type="number" class="form-input" name="exigencia_quantidade_${counter}"
                            step="0.01" required placeholder="1000">
                    </div>
                    <div class="form-group small">
                        <label class="form-label">Unidade *</label>
                        <input type="text" class="form-input" name="exigencia_unidade_${counter}"
                            required placeholder="m2">
                    </div>
                </div>
                <div class="d-flex gap-2 mt-1">
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 0.875rem; color: var(--text-secondary);">
                        <input type="checkbox" name="exigencia_permitir_soma_${counter}" checked>
                        Permitir soma de atestados
                    </label>
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', exigenciaHtml);
        this.atualizarNumerosExigencias();
    },

    removerExigencia(index) {
        const element = document.getElementById(`exigencia-${index}`);
        if (element) {
            element.remove();
            this.atualizarNumerosExigencias();
        }
    },

    atualizarNumerosExigencias() {
        const items = document.querySelectorAll('#listaExigencias .exigencia-item');
        items.forEach((item, i) => {
            const numero = item.querySelector('.exigencia-item-numero');
            if (numero) {
                numero.textContent = `Exigência ${i + 1}`;
            }
        });
    },

    coletarExigencias() {
        const items = document.querySelectorAll('#listaExigencias .exigencia-item');
        const exigencias = [];

        items.forEach(item => {
            const id = item.id.replace('exigencia-', '');
            const descricao = item.querySelector(`[name="exigencia_descricao_${id}"]`)?.value;
            const quantidade = item.querySelector(`[name="exigencia_quantidade_${id}"]`)?.value;
            const unidade = item.querySelector(`[name="exigencia_unidade_${id}"]`)?.value;
            const permitirSoma = item.querySelector(`[name="exigencia_permitir_soma_${id}"]`)?.checked;

            if (descricao && quantidade && unidade) {
                exigencias.push({
                    descricao: descricao,
                    quantidade_minima: parseFloat(quantidade),
                    unidade: unidade,
                    permitir_soma: permitirSoma !== false
                });
            }
        });

        return exigencias;
    },

    // === FORMULARIO MANUAL ===

    setupFormAnaliseManual() {
        const form = document.getElementById('formAnaliseManual');
        if (!form) return;

        const self = this;
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const nomeLicitacao = document.getElementById('nomeLicitacaoManual').value;
            const exigencias = self.coletarExigencias();

            if (exigencias.length === 0) {
                ui.showAlert('Adicione pelo menos uma exigência', 'error');
                return;
            }

            const button = form.querySelector('button[type="submit"]');
            ui.setButtonLoading(button, true, 'btnAnaliseManualText', 'btnAnaliseManualSpinner');

            try {
                const result = await api.post('/analises/manual', {
                    nome_licitacao: nomeLicitacao,
                    exigencias: exigencias
                });

                ui.showAlert('Análise criada com sucesso!', 'success');
                fecharModal('modalNovaAnalise');
                form.reset();
                document.getElementById('listaExigencias').innerHTML = '';
                self.exigenciaCounter = 0;

                // Redirecionar para ver detalhes da analise
                if (result.id) {
                    self.carregarDetalheAnalise(result.id);
                } else {
                    self.carregarAnalises();
                }

            } catch (error) {
                ui.showAlert(error.message || 'Erro ao criar análise', 'error');
            } finally {
                ui.setButtonLoading(button, false, 'btnAnaliseManualText', 'btnAnaliseManualSpinner');
            }
        });
    },

    // === ACOES ===

    async processarAnalise(id) {
        try {
            ui.showAlert('Processando análise...', 'info');
            await api.post(`/analises/${id}/processar`);
            ui.showAlert('Análise processada com sucesso!', 'success');
            this.carregarAnalises();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao processar análise', 'error');
        }
    },

    async excluirAnalise(id) {
        if (!await confirmAction('Tem certeza que deseja excluir esta análise?', { type: 'danger', confirmText: 'Excluir' })) return;

        try {
            await api.delete(`/analises/${id}`);
            ui.showAlert('Análise excluída com sucesso!', 'success');
            this.carregarAnalises();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao excluir análise', 'error');
        }
    }
};

// Inicializar quando DOM estiver pronto (aguarda config carregar)
document.addEventListener('DOMContentLoaded', async () => {
    await loadAuthConfig();
    AnalisesModule.init();

    // Event delegation para acoes dinamicas (cards, exigencias, etc.)
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        const id = btn.dataset.id;
        switch (action) {
            case 'ver-detalhes':
                AnalisesModule.carregarDetalheAnalise(id);
                break;
            case 'processar':
                AnalisesModule.processarAnalise(id);
                break;
            case 'excluir':
                AnalisesModule.excluirAnalise(id);
                break;
            case 'remover-exigencia':
                AnalisesModule.removerExigencia(id);
                break;
        }
    });

    // Event listeners para botoes de pagina (substituem onclick inline)
    const btnNova = document.getElementById('btnNovaAnalise');
    if (btnNova) btnNova.addEventListener('click', () => AnalisesModule.abrirModalNovaAnalise());

    const btnVoltar = document.getElementById('btnVoltarLista');
    if (btnVoltar) btnVoltar.addEventListener('click', () => AnalisesModule.voltarLista());

    const btnExigencia = document.getElementById('btnAdicionarExigencia');
    if (btnExigencia) btnExigencia.addEventListener('click', () => AnalisesModule.adicionarExigencia());

    // Tabs do modal de analise
    document.querySelectorAll('#modalAnaliseTabs .modal-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            AnalisesModule.switchAnaliseTab(tabName);
        });
    });
});
