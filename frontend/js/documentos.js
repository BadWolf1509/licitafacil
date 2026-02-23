// LicitaFacil - Modulo de Gestao Documental
// Gerencia upload, CRUD, filtros, status e checklist de documentos

const TIPO_LABELS = {
    edital: 'Edital',
    certidao_negativa: 'Certidao Negativa',
    balanco: 'Balanco',
    contrato_social: 'Contrato Social',
    procuracao: 'Procuracao',
    declaracao: 'Declaracao',
    planilha: 'Planilha',
    atestado_capacidade: 'Atestado de Capacidade',
    comprovante_endereco: 'Comprovante de Endereco',
    certidao_fgts: 'Certidao FGTS',
    certidao_trabalhista: 'Certidao Trabalhista',
    certidao_federal: 'Certidao Federal',
    certidao_estadual: 'Certidao Estadual',
    certidao_municipal: 'Certidao Municipal',
    outro: 'Outro',
};

const STATUS_DOC_LABELS = {
    valido: 'Valido',
    vencendo: 'Vencendo',
    vencido: 'Vencido',
    nao_aplicavel: 'Nao aplicavel',
};

const STATUS_DOC_BADGES = {
    valido: 'badge-valido',
    vencendo: 'badge-vencendo',
    vencido: 'badge-vencido',
    nao_aplicavel: 'badge-nao-aplicavel',
};

// ============================================
// DocumentosModule
// ============================================
const DocumentosModule = {
    // Estado
    filtros: { tipo_documento: '', status: '', busca: '' },
    paginaAtual: 1,
    licitacoes: [],

    init() {
        this.carregarResumo();
        this.carregarDocumentos();
        this.carregarLicitacoes();
        this.setupEvents();
        this.setupUploadArea();
    },

    // === EVENTOS ===

    setupEvents() {
        const self = this;
        const debouncedLoad = ui.debounce(() => self.carregarDocumentos(1), CONFIG.TIMEOUTS.DEBOUNCE_INPUT);

        // Filtros
        document.getElementById('filtroTipo')?.addEventListener('change', function() {
            self.filtros.tipo_documento = this.value;
            self.carregarDocumentos(1);
        });
        document.getElementById('filtroStatus')?.addEventListener('change', function() {
            self.filtros.status = this.value;
            self.carregarDocumentos(1);
        });
        document.getElementById('filtroBusca')?.addEventListener('input', function() {
            self.filtros.busca = this.value;
            debouncedLoad();
        });

        // Form upload
        document.getElementById('formUploadDocumento')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            await self.uploadDocumento();
        });

        // Form editar
        document.getElementById('formEditarDocumento')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            await self.editarDocumento();
        });
    },

    setupUploadArea() {
        const area = document.getElementById('uploadArea');
        const input = document.getElementById('inputArquivo');
        if (!area || !input) return;

        // Click para abrir seletor
        area.addEventListener('click', () => input.click());

        // Drag & drop
        area.addEventListener('dragover', (e) => {
            e.preventDefault();
            area.classList.add('drag-over');
        });
        area.addEventListener('dragleave', () => {
            area.classList.remove('drag-over');
        });
        area.addEventListener('drop', (e) => {
            e.preventDefault();
            area.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                input.files = e.dataTransfer.files;
                this.mostrarInfoArquivo(e.dataTransfer.files[0]);
            }
        });

        // Selecao de arquivo
        input.addEventListener('change', () => {
            if (input.files.length > 0) {
                this.mostrarInfoArquivo(input.files[0]);
            }
        });
    },

    mostrarInfoArquivo(file) {
        const info = document.getElementById('uploadFileInfo');
        if (!info) return;
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        info.textContent = `Arquivo: ${file.name} (${sizeMB} MB)`;
        info.classList.remove('hidden');
    },

    // === CARREGAR LICITACOES (para selects) ===

    async carregarLicitacoes() {
        try {
            const response = await api.get('/licitacoes/?page_size=200');
            this.licitacoes = response.items || [];
            this.popularSelectsLicitacao();
        } catch (error) {
            console.warn('Erro ao carregar licitacoes para selects:', error);
        }
    },

    popularSelectsLicitacao() {
        const selects = [
            document.getElementById('uploadLicitacao'),
            document.getElementById('editarDocLicitacao'),
            document.getElementById('checklistLicitacao'),
        ];

        selects.forEach(select => {
            if (!select) return;
            const currentValue = select.value;
            // Preservar primeira opcao (Nenhuma / Selecione)
            const firstOption = select.options[0]?.outerHTML || '';
            select.innerHTML = firstOption;
            this.licitacoes.forEach(l => {
                const opt = document.createElement('option');
                opt.value = l.id;
                opt.textContent = `${l.numero} - ${l.orgao}`;
                select.appendChild(opt);
            });
            // Restaurar valor selecionado
            if (currentValue) select.value = currentValue;
        });
    },

    // === RESUMO ===

    async carregarResumo() {
        try {
            const resumo = await api.get('/documentos/resumo');
            this.renderResumoCards(resumo);
        } catch (error) {
            console.warn('Erro ao carregar resumo de documentos:', error);
        }
    },

    renderResumoCards(resumo) {
        const container = document.getElementById('resumoContainer');
        if (!container) return;

        const total = resumo.total || 0;
        const validos = resumo.validos || 0;
        const vencendo = resumo.vencendo || 0;
        const vencidos = resumo.vencidos || 0;

        container.innerHTML = `
            <div class="card doc-resumo-card">
                <div class="doc-resumo-valor">${total}</div>
                <div class="doc-resumo-label">Total</div>
            </div>
            <div class="card doc-resumo-card doc-resumo-valido">
                <div class="doc-resumo-valor">${validos}</div>
                <div class="doc-resumo-label">Validos</div>
            </div>
            <div class="card doc-resumo-card doc-resumo-vencendo">
                <div class="doc-resumo-valor">${vencendo}</div>
                <div class="doc-resumo-label">Vencendo</div>
            </div>
            <div class="card doc-resumo-card doc-resumo-vencido">
                <div class="doc-resumo-valor">${vencidos}</div>
                <div class="doc-resumo-label">Vencidos</div>
            </div>
        `;
    },

    // === LISTAGEM ===

    async carregarDocumentos(page) {
        if (page) this.paginaAtual = page;

        await ErrorHandler.withErrorHandling(async () => {
            const params = new URLSearchParams({
                page: this.paginaAtual,
                page_size: 10,
            });
            if (this.filtros.tipo_documento) params.set('tipo_documento', this.filtros.tipo_documento);
            if (this.filtros.status) params.set('status', this.filtros.status);
            if (this.filtros.busca) params.set('busca', this.filtros.busca);

            const response = await api.get(`/documentos/?${params}`);
            this.renderTabela(response);
            this.renderPagination(response);
        }, 'Erro ao carregar documentos', { container: 'documentosContainer' });
    },

    renderTabela(response) {
        const container = document.getElementById('documentosContainer');
        const documentos = response.items || [];

        if (documentos.length === 0) {
            container.innerHTML = `
                <div class="card empty-state">
                    <h3>Nenhum documento encontrado</h3>
                    <p class="text-muted">Envie seu primeiro documento clicando no botao acima</p>
                </div>
            `;
            return;
        }

        const rows = documentos.map(doc => {
            const tipoLabel = TIPO_LABELS[doc.tipo_documento] || doc.tipo_documento;
            const statusLabel = STATUS_DOC_LABELS[doc.status] || doc.status || 'N/A';
            const badgeClass = STATUS_DOC_BADGES[doc.status] || 'badge-nao-aplicavel';
            const dataEmissao = doc.data_emissao ? new Date(doc.data_emissao).toLocaleDateString('pt-BR') : '-';
            const dataValidade = doc.data_validade ? new Date(doc.data_validade).toLocaleDateString('pt-BR') : '-';
            const licitacaoInfo = doc.licitacao ? Sanitize.escapeHtml(doc.licitacao.numero) : '-';

            return `
                <tr>
                    <td>${Sanitize.escapeHtml(doc.nome)}</td>
                    <td>${Sanitize.escapeHtml(tipoLabel)}</td>
                    <td><span class="badge ${badgeClass}">${Sanitize.escapeHtml(statusLabel)}</span></td>
                    <td>${dataEmissao}</td>
                    <td>${dataValidade}</td>
                    <td>${licitacaoInfo}</td>
                    <td>
                        <div class="d-flex gap-1">
                            ${doc.arquivo_url ? `<a href="${Sanitize.escapeHtml(doc.arquivo_url)}" target="_blank" rel="noopener" class="btn btn-outline btn-sm">Baixar</a>` : ''}
                            <button class="btn btn-outline btn-sm" data-action="editar-doc" data-id="${doc.id}">Editar</button>
                            <button class="btn btn-danger btn-sm" data-action="excluir-doc" data-id="${doc.id}">Excluir</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        container.innerHTML = `
            <div class="table-container">
                <table class="table doc-table">
                    <thead>
                        <tr>
                            <th>Nome</th>
                            <th>Tipo</th>
                            <th>Status</th>
                            <th>Emissao</th>
                            <th>Validade</th>
                            <th>Licitacao</th>
                            <th>Acoes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
    },

    renderPagination(response) {
        const container = document.getElementById('paginationContainer');
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
            html += `<button class="btn btn-outline btn-sm" data-action="pagina" data-page="${this.paginaAtual + 1}">Proximo</button>`;
        }
        container.innerHTML = html;
    },

    // === UPLOAD ===

    async uploadDocumento() {
        const fileInput = document.getElementById('inputArquivo');
        const file = fileInput?.files[0];
        if (!file) {
            ui.showAlert('Selecione um arquivo para enviar.', 'warning');
            return;
        }

        const nome = document.getElementById('uploadNome').value.trim();
        const tipo = document.getElementById('uploadTipo').value;
        if (!nome || !tipo) {
            ui.showAlert('Preencha o nome e tipo do documento.', 'warning');
            return;
        }

        const button = document.querySelector('#formUploadDocumento button[type="submit"]');
        ui.setButtonLoading(button, true, 'btnUploadText', 'btnUploadSpinner');

        try {
            // Montar query params
            const params = new URLSearchParams({ nome, tipo_documento: tipo });

            const licitacaoId = document.getElementById('uploadLicitacao').value;
            if (licitacaoId) params.set('licitacao_id', licitacaoId);

            const dataEmissao = document.getElementById('uploadDataEmissao').value;
            if (dataEmissao) params.set('data_emissao', dataEmissao);

            const dataValidade = document.getElementById('uploadDataValidade').value;
            if (dataValidade) params.set('data_validade', dataValidade);

            const observacoes = document.getElementById('uploadObservacoes').value.trim();
            if (observacoes) params.set('observacoes', observacoes);

            // Upload com FormData (multipart) - usa api.upload
            const formData = new FormData();
            formData.append('arquivo', file);

            await api.upload(`/documentos/upload?${params}`, formData);

            ui.showAlert('Documento enviado com sucesso!', 'success');
            fecharModal('modalUploadDocumento');
            document.getElementById('formUploadDocumento').reset();
            document.getElementById('uploadFileInfo')?.classList.add('hidden');
            this.carregarDocumentos(1);
            this.carregarResumo();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao enviar documento', 'error');
        } finally {
            ui.setButtonLoading(button, false, 'btnUploadText', 'btnUploadSpinner');
        }
    },

    // === EDITAR ===

    async abrirModalEditar(id) {
        try {
            const doc = await api.get(`/documentos/${id}`);

            document.getElementById('editarDocId').value = doc.id;
            document.getElementById('editarDocNome').value = doc.nome || '';
            document.getElementById('editarDocTipo').value = doc.tipo_documento || '';
            document.getElementById('editarDocLicitacao').value = doc.licitacao_id || '';
            document.getElementById('editarDocDataEmissao').value = doc.data_emissao ? doc.data_emissao.substring(0, 10) : '';
            document.getElementById('editarDocDataValidade').value = doc.data_validade ? doc.data_validade.substring(0, 10) : '';
            document.getElementById('editarDocObservacoes').value = doc.observacoes || '';

            document.getElementById('modalEditarDocumento').classList.add('active');
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao carregar documento', 'error');
        }
    },

    async editarDocumento() {
        const id = document.getElementById('editarDocId').value;
        const dados = {
            nome: document.getElementById('editarDocNome').value.trim(),
            tipo_documento: document.getElementById('editarDocTipo').value,
            licitacao_id: document.getElementById('editarDocLicitacao').value || null,
            data_emissao: document.getElementById('editarDocDataEmissao').value || null,
            data_validade: document.getElementById('editarDocDataValidade').value || null,
            observacoes: document.getElementById('editarDocObservacoes').value.trim() || null,
        };

        // Limpar campos vazios
        Object.keys(dados).forEach(k => {
            if (dados[k] === '' || dados[k] === undefined) delete dados[k];
        });

        const button = document.querySelector('#formEditarDocumento button[type="submit"]');
        ui.setButtonLoading(button, true, 'btnEditarDocText', 'btnEditarDocSpinner');

        try {
            await api.put(`/documentos/${id}`, dados);
            ui.showAlert('Documento atualizado com sucesso!', 'success');
            fecharModal('modalEditarDocumento');
            this.carregarDocumentos();
            this.carregarResumo();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao atualizar documento', 'error');
        } finally {
            ui.setButtonLoading(button, false, 'btnEditarDocText', 'btnEditarDocSpinner');
        }
    },

    // === EXCLUIR ===

    async excluirDocumento(id) {
        if (!await confirmAction('Tem certeza que deseja excluir este documento?', { type: 'danger', confirmText: 'Excluir' })) return;

        try {
            await api.delete(`/documentos/${id}`);
            ui.showAlert('Documento excluido com sucesso!', 'success');
            this.carregarDocumentos();
            this.carregarResumo();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao excluir documento', 'error');
        }
    },

    // === MODAL NOVA ===

    abrirModalUpload() {
        document.getElementById('formUploadDocumento')?.reset();
        document.getElementById('uploadFileInfo')?.classList.add('hidden');
        document.getElementById('modalUploadDocumento').classList.add('active');
    },
};

// ============================================
// ChecklistModule
// ============================================
const ChecklistModule = {
    licitacaoId: null,

    init() {
        this.setupEvents();
    },

    setupEvents() {
        const self = this;

        document.getElementById('checklistLicitacao')?.addEventListener('change', function() {
            const id = this.value;
            if (id) {
                self.licitacaoId = id;
                self.carregarChecklist(id);
                self.carregarResumo(id);
            } else {
                self.licitacaoId = null;
                document.getElementById('checklistContainer').innerHTML =
                    '<div class="empty-state"><p class="text-muted">Selecione uma licitacao para ver o checklist</p></div>';
                document.getElementById('checklistResumo')?.classList.add('hidden');
            }
        });
    },

    async carregarChecklist(licitacaoId) {
        const id = licitacaoId || this.licitacaoId;
        if (!id) return;

        await ErrorHandler.withErrorHandling(async () => {
            const items = await api.get(`/documentos/checklist/${id}`);
            this.renderChecklist(items);
        }, 'Erro ao carregar checklist', { container: 'checklistContainer' });
    },

    async carregarResumo(licitacaoId) {
        const id = licitacaoId || this.licitacaoId;
        if (!id) return;

        try {
            const resumo = await api.get(`/documentos/checklist/${id}/resumo`);
            const container = document.getElementById('checklistResumo');
            if (!container) return;

            const total = resumo.total || 0;
            const concluidos = resumo.concluidos || 0;
            const percentual = total > 0 ? Math.round((concluidos / total) * 100) : 0;

            container.classList.remove('hidden');
            container.innerHTML = `
                <div class="checklist-progress-wrapper">
                    <div class="d-flex justify-between align-center mb-1">
                        <span class="text-muted" style="font-size: 0.875rem;">Progresso: ${concluidos}/${total}</span>
                        <span style="font-weight: 600; font-size: 0.875rem;">${percentual}%</span>
                    </div>
                    <div class="checklist-progress">
                        <div class="checklist-progress-bar" style="width: ${percentual}%"></div>
                    </div>
                </div>
            `;
        } catch (error) {
            console.warn('Erro ao carregar resumo do checklist:', error);
        }
    },

    renderChecklist(items) {
        const container = document.getElementById('checklistContainer');
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p class="text-muted">Nenhum item no checklist. Adicione itens obrigatorios.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = items.map(item => {
            const tipoLabel = TIPO_LABELS[item.tipo_documento] || item.tipo_documento;
            const isChecked = item.concluido ? 'checked' : '';
            const obrigatorioClass = item.obrigatorio && !item.concluido ? ' pendente-obrigatorio' : '';
            const concluidoClass = item.concluido ? ' checklist-item-concluido' : '';

            return `
                <div class="checklist-item${obrigatorioClass}${concluidoClass}">
                    <label class="checklist-item-label">
                        <input type="checkbox" ${isChecked}
                            data-action="toggle-checklist"
                            data-item-id="${item.id}"
                            data-concluido="${item.concluido ? '1' : '0'}">
                        <span>${Sanitize.escapeHtml(tipoLabel)}</span>
                        ${item.obrigatorio ? '<span class="badge badge-warning" style="font-size: 0.7rem;">Obrigatorio</span>' : ''}
                    </label>
                    <div class="checklist-item-actions">
                        ${item.documento_id ? `<span class="badge badge-valido" style="font-size: 0.7rem;">Vinculado</span>` : '<span class="text-muted" style="font-size: 0.75rem;">Sem documento</span>'}
                        <button class="btn btn-danger btn-sm" data-action="excluir-checklist-item" data-item-id="${item.id}" style="padding: 2px 8px; font-size: 0.7rem;">X</button>
                    </div>
                </div>
            `;
        }).join('');
    },

    async toggleItem(itemId, currentState) {
        const concluido = currentState === '0';
        try {
            await api.patch(`/documentos/checklist/item/${itemId}`, { concluido });
            if (this.licitacaoId) {
                this.carregarChecklist(this.licitacaoId);
                this.carregarResumo(this.licitacaoId);
            }
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao atualizar item', 'error');
            // Recarregar para restaurar estado
            if (this.licitacaoId) this.carregarChecklist(this.licitacaoId);
        }
    },

    async adicionarItens() {
        if (!this.licitacaoId) {
            ui.showAlert('Selecione uma licitacao primeiro.', 'warning');
            return;
        }

        try {
            await api.post(`/documentos/checklist/${this.licitacaoId}/gerar`, {});
            ui.showAlert('Itens adicionados ao checklist!', 'success');
            this.carregarChecklist(this.licitacaoId);
            this.carregarResumo(this.licitacaoId);
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao adicionar itens', 'error');
        }
    },

    async excluirItem(itemId) {
        if (!await confirmAction('Remover este item do checklist?', { type: 'danger', confirmText: 'Remover' })) return;

        try {
            await api.delete(`/documentos/checklist/item/${itemId}`);
            if (this.licitacaoId) {
                this.carregarChecklist(this.licitacaoId);
                this.carregarResumo(this.licitacaoId);
            }
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao remover item', 'error');
        }
    },

    abrirModal() {
        document.getElementById('checklistLicitacao').value = '';
        document.getElementById('checklistContainer').innerHTML =
            '<div class="empty-state"><p class="text-muted">Selecione uma licitacao para ver o checklist</p></div>';
        document.getElementById('checklistResumo')?.classList.add('hidden');
        this.licitacaoId = null;
        document.getElementById('modalChecklist').classList.add('active');
    },
};

// ============================================
// Inicializacao
// ============================================
document.addEventListener('DOMContentLoaded', async () => {
    await loadAuthConfig();
    DocumentosModule.init();
    ChecklistModule.init();

    // Event delegation para acoes dinamicas
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;

        switch (action) {
            case 'editar-doc':
                DocumentosModule.abrirModalEditar(btn.dataset.id);
                break;
            case 'excluir-doc':
                DocumentosModule.excluirDocumento(btn.dataset.id);
                break;
            case 'pagina':
                DocumentosModule.carregarDocumentos(parseInt(btn.dataset.page));
                break;
            case 'toggle-checklist':
                ChecklistModule.toggleItem(btn.dataset.itemId, btn.dataset.concluido);
                break;
            case 'excluir-checklist-item':
                ChecklistModule.excluirItem(btn.dataset.itemId);
                break;
        }
    });

    // Botao novo documento
    document.getElementById('btnNovoDocumento')?.addEventListener('click', () =>
        DocumentosModule.abrirModalUpload());

    // Botao adicionar itens checklist
    document.getElementById('btnAdicionarItensChecklist')?.addEventListener('click', () =>
        ChecklistModule.adicionarItens());
});
