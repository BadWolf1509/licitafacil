// LicitaFacil - Modulo de Atestados - Entry Point
// Combina todos os sub-modulos e expoe AtestadosModule globalmente

import { formatarTempo, formatarDataSemHora, normalizarUnidade, normalizarDescricaoParaAgrupamento } from './formatters.js';
import {
    getJobStatusLabel,
    getDisplayStatus,
    getJobProgress,
    getJobTimes,
    getJobStateHash,
    getJobFileName,
    formatJobError,
    getEffectivePipeline,
    getPipelineLabel,
    normalizeJobStage,
    getJobStageLabel,
    clearPipelineCache
} from './job-status.js';
import { extrairItemDescricao, parseItemSortKey, compararItens, ordenarServicosPorItem, agruparServicosPorDescricao } from './sorting.js';
import { renderProgressBar, renderJobHtml, updateJobElement, renderProcessingJobsList } from './job-renderer.js';
import { gerarRelatorioAtestado, gerarRelatorioGeral, gerarDetalhesServico } from './relatorios.js';

// Estado global do modulo
const state = {
    cache: [],
    relatorioConsolidadoCache: null,
    resultadoAtestadoCache: null,
    jobsEmProcessamento: new Map(),
    jobTimers: new Map(),
    notifiedJobs: new Set(),
    recentlyCompletedPaths: new Set(),
    openServicosByAtestado: new Set(),
    refreshJobsInterval: null,
    renderScheduled: false,
    lastRenderedJobs: new Map(),
    timeUpdateInterval: null
};

// Modulo principal
const AtestadosModule = {
    // Expor estado para compatibilidade
    get cache() { return state.cache; },
    set cache(val) { state.cache = val; },
    get jobsEmProcessamento() { return state.jobsEmProcessamento; },
    get jobTimers() { return state.jobTimers; },
    get notifiedJobs() { return state.notifiedJobs; },
    get recentlyCompletedPaths() { return state.recentlyCompletedPaths; },
    get openServicosByAtestado() { return state.openServicosByAtestado; },
    get lastRenderedJobs() { return state.lastRenderedJobs; },
    get relatorioConsolidadoCache() { return state.relatorioConsolidadoCache; },
    set relatorioConsolidadoCache(val) { state.relatorioConsolidadoCache = val; },
    get resultadoAtestadoCache() { return state.resultadoAtestadoCache; },
    set resultadoAtestadoCache(val) { state.resultadoAtestadoCache = val; },

    // Inicializacao
    init() {
        this.carregarAtestados();
        this.carregarJobsEmProcessamento();
        this.setupUpload();
        this.setupFormAtestado();
        this.startJobsRefresh();
        this.startJobsRenderer();
        this.startCleanupInterval();
    },

    // Re-exportar funcoes de formatacao
    formatarTempo,
    formatarDataSemHora,
    normalizarUnidade,
    normalizarDescricaoParaAgrupamento,

    // Re-exportar funcoes de status
    getJobStatusLabel,
    getDisplayStatus,
    getJobProgress,
    getJobTimes,
    getJobStateHash,
    getJobFileName,
    formatJobError,
    getEffectivePipeline,
    getPipelineLabel,
    normalizeJobStage,
    getJobStageLabel,

    // Re-exportar funcoes de sorting/parsing
    extrairItemDescricao,
    parseItemSortKey,
    compararItens,
    ordenarServicosPorItem,
    agruparServicosPorDescricao,

    // Re-exportar funcoes de renderizacao
    renderProgressBar,
    renderJobHtml(job) { return renderJobHtml(job, 'AtestadosModule'); },

    // Re-exportar funcoes de relatorios
    gerarRelatorioAtestado,
    gerarRelatorioGeral,

    // === RENDERIZACAO ===

    updateJobElement,

    scheduleRender() {
        if (state.renderScheduled) return;
        state.renderScheduled = true;
        requestAnimationFrame(() => {
            state.renderScheduled = false;
            this.renderProcessingJobs();
        });
    },

    renderProcessingJobs() {
        const jobs = Array.from(state.jobsEmProcessamento.values());
        renderProcessingJobsList(jobs, state.lastRenderedJobs, 'AtestadosModule');
    },

    // === GERENCIAMENTO DE JOBS ===

    upsertJob(job) {
        if (!job || !job.id) return;
        const existing = state.jobsEmProcessamento.get(job.id);
        const merged = existing ? { ...existing, ...job } : job;
        if (!merged.local_created_at) {
            merged.local_created_at = existing?.local_created_at || new Date().toISOString();
        }
        if (!merged.created_at) {
            merged.created_at = merged.local_created_at;
        }
        state.jobsEmProcessamento.set(job.id, merged);
        this.scheduleRender();
    },

    removeJob(jobId) {
        if (!state.jobsEmProcessamento.has(jobId)) return;
        state.jobsEmProcessamento.delete(jobId);
        state.lastRenderedJobs.delete(jobId);
        clearPipelineCache(jobId);
        this.scheduleRender();
    },

    dismissJob(jobId) {
        this.stopMonitoringJob(jobId);
        state.notifiedJobs.delete(jobId);
        this.removeJob(jobId);
    },

    cleanupOrphanedResources() {
        state.jobTimers.forEach((monitor, jobId) => {
            if (!state.jobsEmProcessamento.has(jobId)) {
                this.stopMonitoringJob(jobId);
            }
        });
        state.notifiedJobs.forEach(jobId => {
            if (!state.jobsEmProcessamento.has(jobId)) {
                state.notifiedJobs.delete(jobId);
            }
        });
        state.lastRenderedJobs.forEach((hash, jobId) => {
            if (!state.jobsEmProcessamento.has(jobId)) {
                state.lastRenderedJobs.delete(jobId);
            }
        });
    },

    startCleanupInterval() {
        setInterval(() => this.cleanupOrphanedResources(), 30000);
    },

    markJobCompleted(job) {
        if (job?.file_path) {
            state.recentlyCompletedPaths.add(job.file_path);
            setTimeout(() => {
                state.recentlyCompletedPaths.delete(job.file_path);
                this.carregarAtestados();
            }, 8000);
        }
    },

    async monitorarJob(jobId) {
        if (state.jobTimers.has(jobId)) return;
        const self = this;

        // Handler para processar atualizacoes de job (usado por Realtime e Polling)
        const handleJobUpdate = (job) => {
            if (!job) return;
            job.last_polled_at = new Date().toISOString();
            job.poll_error = null;

            if (job.status === 'completed') {
                self.markJobCompleted(job);
                self.removeJob(jobId);
                self.stopMonitoringJob(jobId);
                ui.showAlert('Atestado processado com sucesso!', 'success');
                self.carregarAtestados();
                return true; // Job finalizado
            }

            if (job.status === 'failed' || job.status === 'cancelled') {
                self.upsertJob(job);
                self.stopMonitoringJob(jobId);
                if (!state.notifiedJobs.has(job.id)) {
                    const msg = job.status === 'cancelled'
                        ? 'Processamento cancelado.'
                        : (formatJobError(job) || 'Falha no processamento do atestado');
                    ui.showAlert(msg, job.status === 'cancelled' ? 'warning' : 'error');
                    state.notifiedJobs.add(job.id);
                }
                return true; // Job finalizado
            }

            self.upsertJob(job);
            return false; // Job ainda em progresso
        };

        // Tentar usar Realtime se disponivel
        if (typeof window.RealtimeModule !== 'undefined' && window.RealtimeModule.isConnected()) {
            console.log(`[MONITOR] Using Realtime for job ${jobId}`);

            const unsubscribe = await window.RealtimeModule.subscribe(jobId, ({ job }) => {
                if (job && job.id === jobId) {
                    handleJobUpdate(job);
                }
            });

            // Armazenar funcao de unsubscribe no lugar do timer
            state.jobTimers.set(jobId, { type: 'realtime', unsubscribe });

            // Fazer poll inicial para ter estado atual
            try {
                const data = await api.get(`/ai/queue/jobs/${jobId}`);
                if (data.job) {
                    handleJobUpdate(data.job);
                }
            } catch (error) {
                console.error('Erro no poll inicial:', error);
            }

            return;
        }

        // Fallback para polling tradicional
        console.log(`[MONITOR] Using polling for job ${jobId}`);
        const poll = async () => {
            try {
                const data = await api.get(`/ai/queue/jobs/${jobId}`);
                handleJobUpdate(data.job);
            } catch (error) {
                console.error('Erro ao consultar job:', error);
                const existing = state.jobsEmProcessamento.get(jobId);
                if (existing) {
                    self.upsertJob({
                        id: jobId,
                        poll_error: 'Falha ao atualizar status. Verifique sua conexao.',
                        last_polled_at: new Date().toISOString()
                    });
                }
            }
        };

        const timerId = setInterval(poll, 3000);
        state.jobTimers.set(jobId, { type: 'polling', timerId });
        await poll();
    },

    stopMonitoringJob(jobId) {
        const monitor = state.jobTimers.get(jobId);
        if (!monitor) return;

        if (monitor.type === 'realtime' && monitor.unsubscribe) {
            monitor.unsubscribe();
        } else if (monitor.type === 'polling' && monitor.timerId) {
            clearInterval(monitor.timerId);
        } else if (typeof monitor === 'number') {
            // Compatibilidade com formato antigo (apenas timerId)
            clearInterval(monitor);
        }

        state.jobTimers.delete(jobId);
    },

    async carregarJobsEmProcessamento() {
        try {
            const data = await api.get('/ai/queue/jobs?limit=20');
            const jobs = (data.jobs || []).filter(j => j.job_type === 'atestado' && j.status !== 'completed');
            jobs.forEach(job => {
                job.last_polled_at = new Date().toISOString();
                job.poll_error = null;
                this.upsertJob(job);
                if (job.status === 'pending' || job.status === 'processing') {
                    this.monitorarJob(job.id);
                }
            });
        } catch (error) {
            console.error('Erro ao carregar jobs:', error);
            ui.showAlert('Falha ao sincronizar o processamento. Tentando novamente...', 'warning');
        }
    },

    async cancelarJob(jobId) {
        if (!confirm('Cancelar o processamento deste atestado?')) return;
        try {
            const data = await api.post(`/ai/queue/jobs/${jobId}/cancel`, {});
            if (data.job) {
                this.upsertJob(data.job);
            }
            ui.showAlert('Processamento cancelado.', 'warning');
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao cancelar processamento', 'error');
        }
    },

    async reprocessarJob(jobId) {
        try {
            const data = await api.post(`/ai/queue/jobs/${jobId}/retry`, {});
            if (data.job) {
                this.removeJob(jobId);
                this.upsertJob(data.job);
                this.monitorarJob(data.job.id);
            }
            ui.showAlert('Reprocessamento iniciado.', 'info');
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao reprocessar', 'error');
        }
    },

    async excluirJob(jobId) {
        if (!confirm('Remover este job da lista?')) return;
        try {
            const data = await api.delete(`/ai/queue/jobs/${jobId}`);
            if (data.deleted) {
                this.removeJob(jobId);
            }
            ui.showAlert('Job removido da lista.', 'success');
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao remover job', 'error');
        }
    },

    startJobsRefresh() {
        if (state.refreshJobsInterval) return;
        state.refreshJobsInterval = setInterval(() => {
            const hasActiveJobs = Array.from(state.jobsEmProcessamento.values())
                .some(job => job.status === 'pending' || job.status === 'processing');
            if (hasActiveJobs) {
                this.carregarJobsEmProcessamento();
            }
        }, 10000);
    },

    startJobsRenderer() {
        if (state.timeUpdateInterval) return;
        state.timeUpdateInterval = setInterval(() => {
            const hasActiveJobs = Array.from(state.jobsEmProcessamento.values())
                .some(job => {
                    const status = getDisplayStatus(job);
                    return status === 'pending' || status === 'processing';
                });

            if (hasActiveJobs) {
                state.jobsEmProcessamento.forEach((job, id) => {
                    const status = getDisplayStatus(job);
                    if (status === 'pending' || status === 'processing') {
                        state.lastRenderedJobs.delete(id);
                    }
                });
                this.scheduleRender();
            }
        }, 5000);
    },

    // === CRUD ATESTADOS ===

    async carregarAtestados() {
        try {
            const response = await api.get('/atestados/?page_size=500');
            const atestados = response.items || [];
            const idsAtestados = new Set(atestados.map((a) => a.id));
            state.openServicosByAtestado.forEach((id) => {
                if (!idsAtestados.has(id)) {
                    state.openServicosByAtestado.delete(id);
                }
            });
            state.cache = atestados;
            const container = document.getElementById('listaAtestados');
            const btnRelatorioGeral = document.getElementById('btnRelatorioGeral');
            const filtroContainer = document.getElementById('filtroAtestadosContainer');
            const filtroInput = document.getElementById('filtroAtestadosInput');
            const filtroContador = document.getElementById('atestadosFiltradosCount');

            btnRelatorioGeral.style.display = atestados.length > 0 ? 'inline-block' : 'none';
            filtroContainer.style.display = atestados.length > 0 ? 'flex' : 'none';

            if (filtroInput) filtroInput.value = '';
            if (filtroContador) filtroContador.textContent = `${atestados.length} atestado(s)`;

            const hasActiveJobs = Array.from(state.jobsEmProcessamento.values())
                .some(job => job.status === 'pending' || job.status === 'processing');

            if (atestados.length === 0) {
                const emptyTitle = hasActiveJobs
                    ? 'Nenhum atestado concluido ainda'
                    : 'Nenhum atestado cadastrado';
                const emptyText = hasActiveJobs
                    ? 'Seus arquivos estao em processamento e aparecerao aqui ao concluir.'
                    : 'Cadastre seu primeiro atestado de capacidade tecnica';
                container.innerHTML = `
                    <div class="card empty-state">
                        <div class="empty-state-icon">&#128203;</div>
                        <h3>${emptyTitle}</h3>
                        <p class="text-muted">${emptyText}</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = atestados.map(a => {
                const searchText = [
                    a.descricao_servico || '',
                    a.contratante || '',
                    a.data_emissao || ''
                ].join(' ').toLowerCase();

                return `
                <div class="card atestado-card-wrapper ${state.recentlyCompletedPaths.has(a.arquivo_path) ? 'atestado-highlight' : ''}"
                     data-atestado-id="${a.id}"
                     data-search="${searchText}">
                    <div class="atestado-card">
                        <div class="atestado-info">
                            <h3>${a.descricao_servico || 'Atestado de Capacidade Tecnica'}</h3>
                            ${a.contratante ? `<p class="text-muted">Contratante: ${a.contratante}</p>` : ''}
                            ${a.data_emissao ? `<p class="text-muted">Emitido em: ${formatarDataSemHora(a.data_emissao)}</p>` : ''}
                            ${a.servicos_json && a.servicos_json.length > 0 ?
                                `<span class="badge">${a.servicos_json.length} servico(s) identificado(s)</span>` :
                                '<span class="badge badge-secondary">Sem servicos detalhados</span>'
                            }
                        </div>
                        <div class="atestado-actions">
                            <button class="btn btn-primary btn-sm" onclick="AtestadosModule.verResultadoConsolidado(${a.id})">Resultado Consolidado</button>
                            <button class="btn btn-outline btn-sm" onclick="AtestadosModule.adicionarServicoItem(${a.id})">+ Item</button>
                            <button class="btn btn-outline btn-sm" onclick="AtestadosModule.editarAtestado(${a.id})">Editar</button>
                            <button class="btn btn-danger btn-sm" onclick="AtestadosModule.excluirAtestado(${a.id})">Excluir</button>
                        </div>
                    </div>
                    ${this.renderizarServicosPreview(a)}
                </div>
            `}).join('');

        } catch (error) {
            ui.showAlert(error.message || 'Erro ao carregar atestados', 'error');
        }
    },

    filtrarAtestados(texto) {
        const container = document.getElementById('listaAtestados');
        if (!container) return;

        const filtro = texto.toLowerCase().trim();
        const cards = container.querySelectorAll('.atestado-card-wrapper');
        let visiveisCount = 0;

        cards.forEach(card => {
            const searchText = card.dataset.search || '';
            const match = !filtro || searchText.includes(filtro);
            card.style.display = match ? '' : 'none';
            if (match) visiveisCount++;
        });

        const contador = document.getElementById('atestadosFiltradosCount');
        if (contador) {
            const total = state.cache.length;
            contador.textContent = filtro
                ? `${visiveisCount} de ${total} atestado(s)`
                : `${total} atestado(s)`;
        }
    },

    setupUpload() {
        const zone = document.getElementById('uploadZone');
        const input = document.getElementById('fileInput');

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
            if (file) this.uploadFile(file);
        });

        input.addEventListener('change', () => {
            if (input.files[0]) {
                this.uploadFile(input.files[0]);
                input.value = '';
            }
        });
    },

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            ui.showAlert('Enviando arquivo...', 'info');
            const result = await api.upload('/atestados/upload', formData);
            fecharModal('modalAtestado');
            ui.showAlert(result.mensagem || 'Arquivo enviado. Processamento iniciado.', 'success');
            if (result.job_id) {
                this.upsertJob({
                    id: result.job_id,
                    status: 'pending',
                    job_type: 'atestado',
                    created_at: new Date().toISOString(),
                    original_filename: file.name,
                    local_created_at: new Date().toISOString()
                });
                this.monitorarJob(result.job_id);
            }
            await this.carregarJobsEmProcessamento();
            this.carregarAtestados();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao enviar arquivo', 'error');
        }
    },

    setupFormAtestado() {
        const form = document.getElementById('formAtestado');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const id = document.getElementById('atId').value;
            const dados = {
                descricao_servico: document.getElementById('atDescricao').value,
                contratante: document.getElementById('atContratante').value || null,
                data_emissao: document.getElementById('atDataEmissao').value || null
            };

            try {
                if (id) {
                    await api.put(`/atestados/${id}`, dados);
                    ui.showAlert('Atestado atualizado com sucesso!', 'success');
                } else {
                    await api.post('/atestados/', dados);
                    ui.showAlert('Atestado cadastrado com sucesso!', 'success');
                }
                fecharModal('modalAtestado');
                this.carregarAtestados();
            } catch (error) {
                ui.showAlert(error.message || 'Erro ao salvar atestado', 'error');
            }
        });
    },

    abrirModalAtestado() {
        document.getElementById('modalAtestadoTitle').textContent = 'Novo Atestado';
        document.getElementById('formAtestado').reset();
        document.getElementById('atId').value = '';
        const tabs = document.getElementById('modalAtestadoTabs');
        if (tabs) {
            tabs.style.display = 'flex';
            switchAtestadoTab('upload');
        }
        abrirModal('modalAtestado');
    },

    async editarAtestado(id) {
        try {
            const atestado = await api.get(`/atestados/${id}`);
            document.getElementById('modalAtestadoTitle').textContent = 'Editar Atestado';
            document.getElementById('atId').value = atestado.id;
            document.getElementById('atDescricao').value = atestado.descricao_servico || '';
            document.getElementById('atContratante').value = atestado.contratante || '';
            document.getElementById('atDataEmissao').value = atestado.data_emissao ? atestado.data_emissao.split('T')[0] : '';
            const tabs = document.getElementById('modalAtestadoTabs');
            if (tabs) {
                tabs.style.display = 'none';
                switchAtestadoTab('manual');
            }
            abrirModal('modalAtestado');
        } catch (error) {
            ui.showAlert('Erro ao carregar atestado', 'error');
        }
    },

    async excluirAtestado(id) {
        if (!confirm('Tem certeza que deseja excluir este atestado?')) return;

        try {
            await api.delete(`/atestados/${id}`);
            state.openServicosByAtestado.delete(id);
            ui.showAlert('Atestado excluido com sucesso!', 'success');
            this.carregarAtestados();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao excluir atestado', 'error');
        }
    },

    // === SERVICOS (ITENS) ===

    async excluirServicoItem(atestadoId, itemIndex) {
        if (!confirm('Excluir este item de servico?')) return;

        try {
            const atestado = await api.get(`/atestados/${atestadoId}`);

            if (!atestado.servicos_json || itemIndex >= atestado.servicos_json.length) {
                ui.showAlert('Item nao encontrado', 'error');
                return;
            }

            const novosServicos = [...atestado.servicos_json];
            novosServicos.splice(itemIndex, 1);

            await api.patch(`/atestados/${atestadoId}/servicos`, {
                servicos_json: novosServicos
            });

            ui.showAlert('Item excluido com sucesso!', 'success');
            this.carregarAtestados();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao excluir item', 'error');
        }
    },

    adicionarServicoItem(atestadoId) {
        document.getElementById('modalServicoTitle').textContent = 'Adicionar Item de Servico';
        document.getElementById('editServicoAtestadoId').value = atestadoId;
        document.getElementById('editServicoIndex').value = -1;
        document.getElementById('editServicoItem').value = '';
        document.getElementById('editServicoDescricao').value = '';
        document.getElementById('editServicoQuantidade').value = '';
        document.getElementById('editServicoUnidade').value = '';
        abrirModal('modalEditarServico');
    },

    async editarServicoItem(atestadoId, itemIndex) {
        try {
            const atestado = await api.get(`/atestados/${atestadoId}`);

            if (!atestado.servicos_json || itemIndex >= atestado.servicos_json.length) {
                ui.showAlert('Item nao encontrado', 'error');
                return;
            }

            const servico = atestado.servicos_json[itemIndex];
            const parsed = extrairItemDescricao(servico);

            document.getElementById('modalServicoTitle').textContent = 'Editar Item de Servico';
            document.getElementById('editServicoAtestadoId').value = atestadoId;
            document.getElementById('editServicoIndex').value = itemIndex;
            document.getElementById('editServicoItem').value = servico.item || parsed.item || '';
            document.getElementById('editServicoDescricao').value = parsed.descricao || '';
            document.getElementById('editServicoQuantidade').value = servico.quantidade || '';
            document.getElementById('editServicoUnidade').value = servico.unidade || '';

            abrirModal('modalEditarServico');
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao carregar item', 'error');
        }
    },

    async salvarServicoItem(event) {
        event.preventDefault();

        const atestadoId = document.getElementById('editServicoAtestadoId').value;
        const itemIndex = parseInt(document.getElementById('editServicoIndex').value);
        const isNew = Number.isNaN(itemIndex) || itemIndex < 0;
        const item = document.getElementById('editServicoItem').value.trim();
        const descricao = document.getElementById('editServicoDescricao').value.trim();
        const quantidade = parseFloat(document.getElementById('editServicoQuantidade').value);
        const unidade = document.getElementById('editServicoUnidade').value.trim();

        if (!descricao || isNaN(quantidade) || !unidade) {
            ui.showAlert('Preencha todos os campos obrigatorios', 'error');
            return;
        }

        try {
            const atestado = await api.get(`/atestados/${atestadoId}`);

            const novosServicos = [...(atestado.servicos_json || [])];
            if (isNew) {
                novosServicos.push({
                    item: item || null,
                    descricao: descricao,
                    quantidade: quantidade,
                    unidade: unidade
                });
            } else {
                if (itemIndex >= novosServicos.length) {
                    ui.showAlert('Item nao encontrado', 'error');
                    return;
                }
                novosServicos[itemIndex] = {
                    item: item || null,
                    descricao: descricao,
                    quantidade: quantidade,
                    unidade: unidade
                };
            }

            await api.patch(`/atestados/${atestadoId}/servicos`, {
                servicos_json: novosServicos
            });

            fecharModal('modalEditarServico');
            ui.showAlert(isNew ? 'Item adicionado com sucesso!' : 'Item atualizado com sucesso!', 'success');
            this.carregarAtestados();
        } catch (error) {
            ui.showAlert(error.message || 'Erro ao salvar item', 'error');
        }
    },

    // === RENDERIZACAO DE SERVICOS ===

    renderizarServicosPreview(atestado) {
        if (!atestado.servicos_json || atestado.servicos_json.length === 0) {
            return '';
        }

        const servicosComIndice = atestado.servicos_json.map((s, idx) => ({ ...s, _originalIndex: idx }));
        const servicosOrdenados = ordenarServicosPorItem(servicosComIndice);
        const isOpen = state.openServicosByAtestado.has(atestado.id);

        const servicosHtml = servicosOrdenados.map((s) => {
            const parsed = extrairItemDescricao(s);
            const itemHtml = parsed.item ? `<span class="servico-item-codigo">${parsed.item}</span>` : '';
            const originalIndex = s._originalIndex;
            return `
                <div class="servico-item" data-index="${originalIndex}">
                    <span class="servico-descricao">${itemHtml}${parsed.descricao}</span>
                    <span class="servico-quantidade">${formatarNumero(s.quantidade)} ${s.unidade}</span>
                    <div class="servico-actions">
                        <button class="servico-btn edit" onclick="AtestadosModule.editarServicoItem(${atestado.id}, ${originalIndex})" title="Editar item">&#9998;</button>
                        <button class="servico-btn delete" onclick="AtestadosModule.excluirServicoItem(${atestado.id}, ${originalIndex})" title="Excluir item">&#10005;</button>
                    </div>
                </div>
            `;
        }).join('');

        const totalServicos = atestado.servicos_json.length;
        return `
            <div style="margin-top: var(--spacing-md);">
                <button class="servicos-toggle" onclick="AtestadosModule.toggleServicos(this, ${atestado.id})">
                    <span class="chevron">${isOpen ? '&#9660;' : '&#9654;'}</span>
                    Ver detalhes (<span id="servicosCount-${atestado.id}">${totalServicos}</span> servico(s))
                </button>
                <div class="servicos-lista ${isOpen ? 'active' : ''}" id="servicosLista-${atestado.id}">
                    <div class="filtro-servicos-inline">
                        <input type="text"
                               class="form-input form-input-sm"
                               placeholder="Filtrar servicos..."
                               oninput="AtestadosModule.filtrarServicosAtestado(${atestado.id}, this.value)"
                               data-total="${totalServicos}">
                    </div>
                    <div class="servicos-container" id="servicosContainer-${atestado.id}">
                        ${servicosHtml}
                    </div>
                </div>
            </div>
        `;
    },

    filtrarServicosAtestado(atestadoId, texto) {
        const container = document.getElementById(`servicosContainer-${atestadoId}`);
        if (!container) return;

        const filtro = texto.toLowerCase().trim();
        const items = container.querySelectorAll('.servico-item');
        let visiveisCount = 0;

        items.forEach(item => {
            const descricao = item.querySelector('.servico-descricao').textContent.toLowerCase();
            const match = !filtro || descricao.includes(filtro);
            item.style.display = match ? '' : 'none';
            if (match) visiveisCount++;
        });

        const contador = document.getElementById(`servicosCount-${atestadoId}`);
        const input = container.parentElement.querySelector('input[data-total]');
        if (contador && input) {
            const total = parseInt(input.dataset.total, 10);
            contador.textContent = filtro ? `${visiveisCount} de ${total}` : `${total}`;
        }
    },

    toggleServicos(btn, atestadoId) {
        const lista = btn.nextElementSibling;
        const chevron = btn.querySelector('.chevron');

        const isOpen = lista.classList.toggle('active');
        chevron.innerHTML = isOpen ? '&#9660;' : '&#9654;';
        if (atestadoId !== undefined && atestadoId !== null) {
            if (isOpen) {
                state.openServicosByAtestado.add(atestadoId);
            } else {
                state.openServicosByAtestado.delete(atestadoId);
            }
        }
    },

    // === RELATORIOS ===

    async verResultadoConsolidado(id) {
        try {
            const atestado = await api.get(`/atestados/${id}`);
            const content = document.getElementById('resultadoContent');
            const servicos = atestado.servicos_json || [];
            const servicosConsolidados = agruparServicosPorDescricao(servicos);

            state.resultadoAtestadoCache = { atestado, servicosConsolidados };

            content.innerHTML = gerarRelatorioAtestado(atestado, servicosConsolidados);
            abrirModal('modalResultado');
        } catch (error) {
            ui.showAlert('Erro ao carregar resultado', 'error');
        }
    },

    filtrarServicosResultado(texto) {
        if (!state.resultadoAtestadoCache) return;

        const filtro = texto.toLowerCase().trim();
        const tbody = document.getElementById('tabelaServicosResultado');
        if (!tbody) return;

        const rows = tbody.querySelectorAll('tr[data-servico-idx]');
        let visiveisCount = 0;

        rows.forEach(row => {
            const descricao = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
            const match = !filtro || descricao.includes(filtro);
            row.style.display = match ? '' : 'none';
            if (match) visiveisCount++;
        });

        const contador = document.getElementById('servicosResultadoCount');
        if (contador) {
            const total = state.resultadoAtestadoCache.servicosConsolidados.length;
            contador.textContent = filtro ? `${visiveisCount} de ${total}` : `${total}`;
        }
    },

    async abrirRelatorioGeral() {
        const content = document.getElementById('relatorioGeralContent');
        content.innerHTML = '<div class="loading-spinner">Carregando todos os atestados...</div>';
        abrirModal('modalRelatorioGeral');

        try {
            const response = await api.get('/atestados/?page_size=500');
            const todosAtestados = response.items || [];

            const atestadosMap = new Map();
            todosAtestados.forEach(a => atestadosMap.set(a.id, a));

            let totalServicos = 0;
            let todosServicos = [];
            todosAtestados.forEach(a => {
                if (a.servicos_json && a.servicos_json.length > 0) {
                    totalServicos += a.servicos_json.length;
                    const servicosComRef = a.servicos_json.map(s => ({
                        ...s,
                        _atestado_id: a.id
                    }));
                    todosServicos = todosServicos.concat(servicosComRef);
                }
            });

            const servicosConsolidados = agruparServicosPorDescricao(todosServicos, atestadosMap);

            state.relatorioConsolidadoCache = {
                atestados: todosAtestados,
                totalServicos: totalServicos,
                servicosConsolidados: servicosConsolidados
            };

            content.innerHTML = gerarRelatorioGeral(state.relatorioConsolidadoCache);

        } catch (error) {
            content.innerHTML = `<div class="alert alert-danger">Erro ao carregar atestados: ${error.message}</div>`;
        }
    },

    filtrarServicosConsolidados(texto) {
        if (!state.relatorioConsolidadoCache) return;

        const filtro = texto.toLowerCase().trim();
        const tbody = document.getElementById('tabelaServicosConsolidados');
        const rows = tbody.querySelectorAll('tr[data-servico-idx]');
        let visiveisCount = 0;

        rows.forEach(row => {
            const descricao = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
            const match = !filtro || descricao.includes(filtro);
            row.style.display = match ? '' : 'none';
            if (match) visiveisCount++;
        });

        const contador = document.getElementById('servicosFiltradosCount');
        if (contador) {
            const total = state.relatorioConsolidadoCache.servicosConsolidados.length;
            contador.textContent = filtro ? `${visiveisCount} de ${total}` : `${total}`;
        }
    },

    mostrarDetalhesServico(idx) {
        if (!state.relatorioConsolidadoCache) return;

        const servico = state.relatorioConsolidadoCache.servicosConsolidados[idx];
        if (!servico) return;

        const content = document.getElementById('detalhesServicoContent');
        content.innerHTML = gerarDetalhesServico(servico, formatarDataSemHora);

        abrirModal('modalDetalhesServico');
    },

    verAtestado(id) {
        fecharModal('modalDetalhesServico');
        fecharModal('modalRelatorioGeral');
        this.verResultadoConsolidado(id);
    }
};

// Expor globalmente para compatibilidade com HTML
if (typeof window !== 'undefined') {
    window.AtestadosModule = AtestadosModule;
}

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => AtestadosModule.init());

export default AtestadosModule;
