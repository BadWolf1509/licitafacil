// LicitaFacil - Modulo de Atestados
// Gerencia CRUD, upload, processamento e relatorios de atestados

const AtestadosModule = {
    // Estado
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
    lastKnownPipeline: new Map(),
    timeUpdateInterval: null,

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

    // === FORMATACAO E UTILIDADES ===

    formatarTempo(ms) {
        const total = Math.max(0, Math.floor(ms / 1000));
        const min = Math.floor(total / 60);
        const sec = total % 60;
        return `${min}m ${sec.toString().padStart(2, '0')}s`;
    },

    formatarDataSemHora(dataStr) {
        if (!dataStr) return '';
        const data = new Date(dataStr);
        return data.toLocaleDateString('pt-BR');
    },

    parseJobTime(value) {
        if (!value) return null;
        const time = Date.parse(value);
        return Number.isNaN(time) ? null : time;
    },

    getJobTimes(job) {
        const createdAt = this.parseJobTime(job.created_at);
        const localCreatedAt = this.parseJobTime(job.local_created_at);
        let startedAt = this.parseJobTime(job.started_at);
        const endedAt = this.parseJobTime(job.completed_at || job.canceled_at);
        const now = Date.now();

        let effectiveCreatedAt = createdAt;
        if (!effectiveCreatedAt || effectiveCreatedAt > now + 2000) {
            effectiveCreatedAt = localCreatedAt;
        }
        if (!effectiveCreatedAt && startedAt) {
            effectiveCreatedAt = startedAt;
        }

        if (!effectiveCreatedAt) {
            return { queueMs: 0, processingMs: 0, hasQueue: false, hasProcessing: false };
        }

        const displayStatus = this.getDisplayStatus(job);
        if (!startedAt && displayStatus === 'processing') {
            startedAt = effectiveCreatedAt || now;
        }

        if (!startedAt) {
            return {
                queueMs: Math.max(0, now - effectiveCreatedAt),
                processingMs: 0,
                hasQueue: true,
                hasProcessing: false
            };
        }

        if (effectiveCreatedAt > startedAt) {
            effectiveCreatedAt = startedAt;
        }
        const queueMs = Math.max(0, startedAt - effectiveCreatedAt);
        const processingMs = Math.max(0, (endedAt || now) - startedAt);
        return {
            queueMs,
            processingMs,
            hasQueue: true,
            hasProcessing: true
        };
    },

    // === STATUS E LABELS ===

    getJobStatusLabel(status) {
        const labels = {
            pending: 'Na fila',
            processing: 'Processando',
            failed: 'Falhou',
            cancelled: 'Cancelado',
            completed: 'Concluido'
        };
        return labels[status] || 'Processando';
    },

    getPipelineFromStage(stage) {
        const stagePipeline = {
            'queued': null,
            'pending': null,
            'processing': null,
            'texto': 'NATIVE_TEXT',
            'ocr': 'LOCAL_OCR',
            'vision': 'VISION_AI',
            'ia': null,
            'final': null,
            'merge': null,
            'save': null
        };
        return stagePipeline[stage] || null;
    },

    getEffectivePipeline(job) {
        if (job.pipeline) {
            this.lastKnownPipeline.set(job.id, job.pipeline);
            return job.pipeline;
        }
        const currentPipeline = this.getPipelineFromStage(job.progress_stage);
        if (currentPipeline) {
            this.lastKnownPipeline.set(job.id, currentPipeline);
            return currentPipeline;
        }
        return this.lastKnownPipeline.get(job.id) || null;
    },

    getPipelineLabel(pipeline) {
        const labels = {
            'NATIVE_TEXT': 'Extracao Nativa',
            'LOCAL_OCR': 'OCR Local',
            'CLOUD_OCR': 'OCR Cloud (Azure)',
            'VISION_AI': 'GPT-4o Vision'
        };
        return labels[pipeline] || pipeline;
    },

    normalizeJobStage(stage, status) {
        const normalized = (stage || '').toString().toLowerCase();
        if (!normalized || normalized === 'pending' || normalized === 'queued') {
            return status === 'pending' ? 'queued' : 'processing';
        }
        if (normalized === 'finalizar' || normalized === 'finalizando') {
            return 'final';
        }
        return normalized;
    },

    getDisplayStatus(job) {
        const raw = (job?.status || '').toString().toLowerCase();
        if (raw === 'failed' || raw === 'cancelled' || raw === 'completed') {
            return raw;
        }
        const stage = this.normalizeJobStage(job?.progress_stage, raw);
        const hasStarted = Boolean(job?.started_at);
        const hasProgress = Number(job?.progress_current) > 0 || Number(job?.progress_total) > 0;
        if (raw === 'pending' && (hasStarted || hasProgress || stage !== 'queued')) {
            return 'processing';
        }
        if (!raw || raw === 'queued') {
            return 'pending';
        }
        return raw;
    },

    getJobStageLabel(stage, status) {
        const labels = {
            queued: 'Aguardando',
            pending: 'Aguardando',
            processing: 'Iniciando',
            texto: 'Extraindo texto (PDF nativo)',
            ocr: 'Executando OCR',
            vision: 'Processando imagens',
            ia: 'Analisando com IA',
            final: 'Finalizando',
            merge: 'Consolidando dados',
            save: 'Salvando resultado'
        };
        return labels[stage] || (status === 'pending' ? 'Aguardando' : 'Processando');
    },

    getJobProgress(job) {
        const total = Number(job.progress_total) || 0;
        const current = Number(job.progress_current) || 0;
        const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
        const displayStatus = this.getDisplayStatus(job);
        const stage = this.normalizeJobStage(job.progress_stage, displayStatus);
        const stageLabel = this.getJobStageLabel(stage, displayStatus);
        const message = job.progress_message || stageLabel;
        return { total, current, percent, stage, stageLabel, message, displayStatus };
    },

    getJobFileName(job) {
        if (job.original_filename) return job.original_filename;
        if (!job.file_path) return 'arquivo';
        const parts = job.file_path.split(/[\\/]/);
        return parts[parts.length - 1] || 'arquivo';
    },

    formatJobError(job) {
        if (!job || !job.error) return '';
        const raw = String(job.error);
        const lines = raw.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
        if (!lines.length) return '';
        const errorLine = [...lines].reverse().find(line => /error|exception|falha/i.test(line))
            || lines[lines.length - 1];
        const cleaned = errorLine.replace(/^erro\s*:?\s*/i, '').trim();
        if (!cleaned) return '';
        return cleaned.length > 180 ? `${cleaned.slice(0, 177)}...` : cleaned;
    },

    getJobStateHash(job) {
        const progress = this.getJobProgress(job);
        const times = this.getJobTimes(job);
        return JSON.stringify({
            status: this.getDisplayStatus(job),
            progress: progress.percent,
            stage: progress.stage,
            message: progress.message,
            error: job.error,
            poll_error: job.poll_error,
            queueMs: Math.floor(times.queueMs / 1000),
            processingMs: Math.floor(times.processingMs / 1000)
        });
    },

    // === RENDERIZACAO DE JOBS ===

    renderProgressBar(job) {
        const progress = this.getJobProgress(job);
        const displayStatus = progress.displayStatus;
        if (displayStatus === 'failed' || displayStatus === 'cancelled') {
            return '';
        }
        const indeterminate = progress.total <= 0 || progress.current <= 0;
        const width = indeterminate ? '40%' : `${progress.percent}%`;
        const statusClass = displayStatus === 'pending' ? 'pending' : 'processing';
        return `
            <div class="processing-progress ${statusClass} ${indeterminate ? 'indeterminate' : ''}">
                <div class="processing-progress-bar" style="width: ${width};"></div>
            </div>
        `;
    },

    renderJobHtml(job) {
        const displayStatus = this.getDisplayStatus(job);
        const statusLabel = this.getJobStatusLabel(displayStatus);
        const progress = this.getJobProgress(job);
        const progressText = progress.total > 0 ? `${progress.current}/${progress.total} (${progress.percent}%)` : '';
        const times = this.getJobTimes(job);

        const queueTimeText = displayStatus === 'pending' && times.hasQueue
            ? `Fila: ${this.formatarTempo(times.queueMs)}`
            : '';

        const processingTimeText = displayStatus === 'processing'
            ? `Tempo: ${this.formatarTempo(times.processingMs)}`
            : '';

        const pipeline = this.getEffectivePipeline(job);
        const pipelineText = displayStatus === 'processing' && pipeline
            ? `Pipeline: ${this.getPipelineLabel(pipeline)}`
            : '';

        const showStage = displayStatus === 'processing';
        const stageText = showStage ? progress.stageLabel : '';

        const metaItems = [
            queueTimeText ? `<span class="job-meta-item">&#9201; ${queueTimeText}</span>` : '',
            processingTimeText ? `<span class="job-meta-item">&#9201; ${processingTimeText}</span>` : '',
            pipelineText ? `<span class="job-meta-item">&#128202; ${pipelineText}</span>` : '',
            stageText ? `<span class="job-meta-item">&#128260; ${stageText}</span>` : '',
            progressText ? `<span class="job-meta-item">&#128200; ${progressText}</span>` : ''
        ].filter(Boolean).join('');

        const fileName = this.getJobFileName(job);
        const syncError = job.poll_error ? `<div class="processing-job-error">${job.poll_error}</div>` : '';
        const errorMessage = this.formatJobError(job);
        const errorHtml = displayStatus === 'failed' && errorMessage
            ? `<div class="processing-job-error">${errorMessage}</div>`
            : '';
        const actionHtml = displayStatus === 'failed' || displayStatus === 'cancelled'
            ? `
                <button class="btn btn-outline btn-sm" onclick="AtestadosModule.reprocessarJob('${job.id}')">Tentar novamente</button>
                <button class="btn btn-outline btn-sm" onclick="AtestadosModule.excluirJob('${job.id}')">Remover</button>
            `
            : `<button class="btn btn-outline btn-sm" onclick="AtestadosModule.cancelarJob('${job.id}')">Cancelar</button>`;

        return `
            <div class="processing-job-info">
                <div class="processing-job-head">
                    <div class="processing-job-title" title="${fileName}">${fileName}</div>
                    <span class="job-status ${displayStatus}">${statusLabel}</span>
                </div>
                <div class="processing-job-meta">
                    ${metaItems}
                </div>
                ${this.renderProgressBar(job)}
                ${syncError}
                ${errorHtml}
            </div>
            <div class="processing-job-actions">
                ${actionHtml}
            </div>
        `;
    },

    updateJobElement(job) {
        const jobElement = document.querySelector(`[data-job-id="${job.id}"]`);
        if (!jobElement) return false;

        const displayStatus = this.getDisplayStatus(job);
        jobElement.className = `processing-job ${displayStatus}`;
        jobElement.innerHTML = this.renderJobHtml(job);
        return true;
    },

    scheduleRender() {
        if (this.renderScheduled) return;
        this.renderScheduled = true;
        requestAnimationFrame(() => {
            this.renderScheduled = false;
            this.renderProcessingJobs();
        });
    },

    renderProcessingJobs() {
        const container = document.getElementById('processingJobs');
        if (!container) return;
        const jobs = Array.from(this.jobsEmProcessamento.values());

        if (jobs.length === 0) {
            if (container.innerHTML !== '') {
                container.innerHTML = '';
                this.lastRenderedJobs.clear();
            }
            return;
        }

        const currentJobIds = new Set(jobs.map(j => j.id));
        const renderedJobIds = new Set(this.lastRenderedJobs.keys());
        const needsFullRebuild =
            currentJobIds.size !== renderedJobIds.size ||
            ![...currentJobIds].every(id => renderedJobIds.has(id)) ||
            !container.querySelector('.processing-job');

        if (needsFullRebuild) {
            const queuedCount = jobs.filter(job => this.getDisplayStatus(job) === 'pending').length;
            const processingCount = jobs.filter(job => this.getDisplayStatus(job) === 'processing').length;
            const attentionCount = jobs.filter(job => {
                const status = this.getDisplayStatus(job);
                return status === 'failed' || status === 'cancelled';
            }).length;
            const summaryParts = [];
            if (queuedCount > 0) summaryParts.push(`${queuedCount} na fila`);
            if (processingCount > 0) summaryParts.push(`${processingCount} processando`);
            if (attentionCount > 0) summaryParts.push(`${attentionCount} com atencao`);
            const summaryText = summaryParts.join(' | ');

            const jobsHtml = jobs.map(job => {
                const displayStatus = this.getDisplayStatus(job);
                return `
                    <div class="processing-job ${displayStatus}" data-job-id="${job.id}">
                        ${this.renderJobHtml(job)}
                    </div>
                `;
            }).join('');

            container.innerHTML = `
                <div class="card">
                    <div class="processing-header">
                        <h2 class="processing-header-title">Processamento de atestados</h2>
                        <p class="processing-header-subtitle" data-summary>${summaryText}</p>
                    </div>
                    <div class="processing-jobs-list">
                        ${jobsHtml}
                    </div>
                </div>
            `;

            this.lastRenderedJobs.clear();
            jobs.forEach(job => {
                this.lastRenderedJobs.set(job.id, this.getJobStateHash(job));
            });
        } else {
            let hasChanges = false;
            jobs.forEach(job => {
                const currentHash = this.getJobStateHash(job);
                const lastHash = this.lastRenderedJobs.get(job.id);

                if (currentHash !== lastHash) {
                    this.updateJobElement(job);
                    this.lastRenderedJobs.set(job.id, currentHash);
                    hasChanges = true;
                }
            });

            if (hasChanges) {
                const summaryElement = container.querySelector('[data-summary]');
                if (summaryElement) {
                    const queuedCount = jobs.filter(job => this.getDisplayStatus(job) === 'pending').length;
                    const processingCount = jobs.filter(job => this.getDisplayStatus(job) === 'processing').length;
                    const attentionCount = jobs.filter(job => {
                        const status = this.getDisplayStatus(job);
                        return status === 'failed' || status === 'cancelled';
                    }).length;
                    const summaryParts = [];
                    if (queuedCount > 0) summaryParts.push(`${queuedCount} na fila`);
                    if (processingCount > 0) summaryParts.push(`${processingCount} processando`);
                    if (attentionCount > 0) summaryParts.push(`${attentionCount} com atencao`);
                    summaryElement.textContent = summaryParts.join(' | ');
                }
            }
        }
    },

    // === GERENCIAMENTO DE JOBS ===

    upsertJob(job) {
        if (!job || !job.id) return;
        const existing = this.jobsEmProcessamento.get(job.id);
        const merged = existing ? { ...existing, ...job } : job;
        if (!merged.local_created_at) {
            merged.local_created_at = existing?.local_created_at || new Date().toISOString();
        }
        if (!merged.created_at) {
            merged.created_at = merged.local_created_at;
        }
        this.jobsEmProcessamento.set(job.id, merged);
        this.scheduleRender();
    },

    removeJob(jobId) {
        if (!this.jobsEmProcessamento.has(jobId)) return;
        this.jobsEmProcessamento.delete(jobId);
        this.lastRenderedJobs.delete(jobId);
        this.lastKnownPipeline.delete(jobId);
        this.scheduleRender();
    },

    dismissJob(jobId) {
        if (this.jobTimers.has(jobId)) {
            clearInterval(this.jobTimers.get(jobId));
            this.jobTimers.delete(jobId);
        }
        this.notifiedJobs.delete(jobId);
        this.removeJob(jobId);
    },

    cleanupOrphanedResources() {
        this.jobTimers.forEach((timer, jobId) => {
            if (!this.jobsEmProcessamento.has(jobId)) {
                clearInterval(timer);
                this.jobTimers.delete(jobId);
            }
        });

        this.notifiedJobs.forEach(jobId => {
            if (!this.jobsEmProcessamento.has(jobId)) {
                this.notifiedJobs.delete(jobId);
            }
        });

        this.lastRenderedJobs.forEach((hash, jobId) => {
            if (!this.jobsEmProcessamento.has(jobId)) {
                this.lastRenderedJobs.delete(jobId);
            }
        });
    },

    startCleanupInterval() {
        setInterval(() => this.cleanupOrphanedResources(), 30000);
    },

    markJobCompleted(job) {
        if (job?.file_path) {
            this.recentlyCompletedPaths.add(job.file_path);
            setTimeout(() => {
                this.recentlyCompletedPaths.delete(job.file_path);
                this.carregarAtestados();
            }, 8000);
        }
    },

    async monitorarJob(jobId) {
        if (this.jobTimers.has(jobId)) return;
        const self = this;
        const poll = async () => {
            try {
                const data = await api.get(`/ai/queue/jobs/${jobId}`);
                const job = data.job;
                if (!job) return;
                job.last_polled_at = new Date().toISOString();
                job.poll_error = null;
                if (job.status === 'completed') {
                    self.markJobCompleted(job);
                    self.removeJob(jobId);
                    clearInterval(self.jobTimers.get(jobId));
                    self.jobTimers.delete(jobId);
                    ui.showAlert('Atestado processado com sucesso!', 'success');
                    self.carregarAtestados();
                    return;
                }
                if (job.status === 'failed' || job.status === 'cancelled') {
                    self.upsertJob(job);
                    clearInterval(self.jobTimers.get(jobId));
                    self.jobTimers.delete(jobId);
                    if (!self.notifiedJobs.has(job.id)) {
                        const msg = job.status === 'cancelled'
                            ? 'Processamento cancelado.'
                            : (self.formatJobError(job) || 'Falha no processamento do atestado');
                        ui.showAlert(msg, job.status === 'cancelled' ? 'warning' : 'error');
                        self.notifiedJobs.add(job.id);
                    }
                    return;
                }
                self.upsertJob(job);
            } catch (error) {
                console.error('Erro ao consultar job:', error);
                const existing = self.jobsEmProcessamento.get(jobId);
                if (existing) {
                    self.upsertJob({
                        id: jobId,
                        poll_error: 'Falha ao atualizar status. Verifique sua conexao.',
                        last_polled_at: new Date().toISOString()
                    });
                }
            }
        };
        this.jobTimers.set(jobId, setInterval(poll, 3000));
        await poll();
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
        if (this.refreshJobsInterval) return;
        this.refreshJobsInterval = setInterval(() => {
            const hasActiveJobs = Array.from(this.jobsEmProcessamento.values())
                .some(job => job.status === 'pending' || job.status === 'processing');
            if (hasActiveJobs) {
                this.carregarJobsEmProcessamento();
            }
        }, 10000);
    },

    startJobsRenderer() {
        if (this.timeUpdateInterval) return;
        this.timeUpdateInterval = setInterval(() => {
            const hasActiveJobs = Array.from(this.jobsEmProcessamento.values())
                .some(job => {
                    const status = this.getDisplayStatus(job);
                    return status === 'pending' || status === 'processing';
                });

            if (hasActiveJobs) {
                this.jobsEmProcessamento.forEach((job, id) => {
                    const status = this.getDisplayStatus(job);
                    if (status === 'pending' || status === 'processing') {
                        this.lastRenderedJobs.delete(id);
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
            this.openServicosByAtestado.forEach((id) => {
                if (!idsAtestados.has(id)) {
                    this.openServicosByAtestado.delete(id);
                }
            });
            this.cache = atestados;
            const container = document.getElementById('listaAtestados');
            const btnRelatorioGeral = document.getElementById('btnRelatorioGeral');
            const filtroContainer = document.getElementById('filtroAtestadosContainer');
            const filtroInput = document.getElementById('filtroAtestadosInput');
            const filtroContador = document.getElementById('atestadosFiltradosCount');

            btnRelatorioGeral.style.display = atestados.length > 0 ? 'inline-block' : 'none';
            filtroContainer.style.display = atestados.length > 0 ? 'flex' : 'none';

            // Limpar filtro ao recarregar
            if (filtroInput) filtroInput.value = '';
            if (filtroContador) filtroContador.textContent = `${atestados.length} atestado(s)`;

            const hasActiveJobs = Array.from(this.jobsEmProcessamento.values())
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
                <div class="card atestado-card-wrapper ${this.recentlyCompletedPaths.has(a.arquivo_path) ? 'atestado-highlight' : ''}"
                     data-atestado-id="${a.id}"
                     data-search="${searchText}">
                    <div class="atestado-card">
                        <div class="atestado-info">
                            <h3>${a.descricao_servico || 'Atestado de Capacidade Tecnica'}</h3>
                            ${a.contratante ? `<p class="text-muted">Contratante: ${a.contratante}</p>` : ''}
                            ${a.data_emissao ? `<p class="text-muted">Emitido em: ${this.formatarDataSemHora(a.data_emissao)}</p>` : ''}
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
            const total = this.cache.length;
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
            // Fechar o modal apos envio bem-sucedido
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
        // Mostrar tabs e resetar para upload
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
            // Ocultar tabs e mostrar apenas formulario
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
            this.openServicosByAtestado.delete(id);
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
            const parsed = this.extrairItemDescricao(servico);

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
        const servicosOrdenados = this.ordenarServicosPorItem(servicosComIndice);
        const isOpen = this.openServicosByAtestado.has(atestado.id);

        const servicosHtml = servicosOrdenados.map((s) => {
            const parsed = this.extrairItemDescricao(s);
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
                this.openServicosByAtestado.add(atestadoId);
            } else {
                this.openServicosByAtestado.delete(atestadoId);
            }
        }
    },

    // === UTILIDADES DE PARSING ===

    extrairItemDescricao(servico) {
        const descricaoOriginal = (servico?.descricao || '').toString();
        if (servico?.item) {
            return { item: servico.item, descricao: descricaoOriginal };
        }

        const itemRegex = /^(S\d+-|AD\d*-)?(\d{1,3}(?:\s*\.\s*\d{1,3}){1,3}|\d{1,3}(?:\s+\d{1,2}){1,3})\s*/i;
        const match = descricaoOriginal.match(itemRegex);
        if (!match) {
            return { item: null, descricao: descricaoOriginal };
        }

        const prefix = (match[1] || '').toUpperCase();
        const itemBase = match[2]
            .replace(/\s+/g, '.')
            .replace(/\.+/g, '.')
            .replace(/^\.+|\.+$/g, '');
        const item = `${prefix}${itemBase}`;
        const descricao = descricaoOriginal.replace(itemRegex, '').trim();
        return { item, descricao: descricao || descricaoOriginal };
    },

    normalizarUnidade(unidade) {
        return (unidade || '')
            .toString()
            .toUpperCase()
            .replace(/\u00b2/g, '2')
            .replace(/\u00b3/g, '3')
            .replace('M^2', 'M2')
            .replace('M^3', 'M3')
            .replace(/\s+/g, '');
    },

    normalizarDescricaoParaAgrupamento(descricao) {
        return (descricao || '')
            .toString()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toUpperCase()
            .replace(/[^A-Z0-9]+/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    },

    parseItemSortKey(item) {
        const raw = (item || '').toString().trim();
        if (!raw) {
            return { prefixWeight: 99, prefixValue: 0, parts: [], suffix: 0, raw: '' };
        }

        let prefixWeight = 0;
        let prefixValue = 0;
        let core = raw;

        const restartMatch = core.match(/^S(\d+)-(.+)$/i);
        if (restartMatch) {
            prefixWeight = 1;
            prefixValue = parseInt(restartMatch[1], 10) || 0;
            core = restartMatch[2].trim();
        }

        const aditivoMatch = core.match(/^AD(\d*)-(.+)$/i);
        if (aditivoMatch) {
            prefixWeight = 2;
            prefixValue = aditivoMatch[1] ? parseInt(aditivoMatch[1], 10) : 1;
            core = aditivoMatch[2].trim();
        }

        let suffix = 0;
        const suffixMatch = core.match(/^(.+)-([A-Z])$/i);
        if (suffixMatch) {
            core = suffixMatch[1].trim();
            suffix = suffixMatch[2].toUpperCase().charCodeAt(0) - 64;
        }

        const parts = core.split('.').map(part => {
            const digits = part.replace(/\D/g, '');
            return digits ? parseInt(digits, 10) : 0;
        });

        return { prefixWeight, prefixValue, parts, suffix, raw };
    },

    compararItens(a, b) {
        const itemA = (this.extrairItemDescricao(a).item || '').toString();
        const itemB = (this.extrairItemDescricao(b).item || '').toString();

        if (!itemA && !itemB) return 0;
        if (!itemA) return 1;
        if (!itemB) return -1;

        const keyA = this.parseItemSortKey(itemA);
        const keyB = this.parseItemSortKey(itemB);

        if (keyA.prefixWeight !== keyB.prefixWeight) {
            return keyA.prefixWeight - keyB.prefixWeight;
        }
        if (keyA.prefixValue !== keyB.prefixValue) {
            return keyA.prefixValue - keyB.prefixValue;
        }

        const maxLen = Math.max(keyA.parts.length, keyB.parts.length);
        for (let i = 0; i < maxLen; i += 1) {
            const partA = keyA.parts[i] ?? 0;
            const partB = keyB.parts[i] ?? 0;
            if (partA !== partB) {
                return partA - partB;
            }
        }

        if (keyA.suffix !== keyB.suffix) {
            return keyA.suffix - keyB.suffix;
        }

        return itemA.localeCompare(itemB, 'pt-BR', { numeric: true });
    },

    ordenarServicosPorItem(servicos) {
        return [...servicos].sort((a, b) => this.compararItens(a, b));
    },

    agruparServicosPorDescricao(servicos, atestadosMap = null) {
        const agrupados = {};
        servicos.forEach(s => {
            const parsed = this.extrairItemDescricao(s);
            const unidade = this.normalizarUnidade(s.unidade);
            const descricaoKey = this.normalizarDescricaoParaAgrupamento(parsed.descricao);
            const chave = `${descricaoKey || (parsed.descricao || '').toUpperCase().trim()}|||${unidade}`;
            if (!agrupados[chave]) {
                agrupados[chave] = {
                    descricao: parsed.descricao,
                    unidade: unidade,
                    quantidade: 0,
                    atestados: []
                };
            } else if (parsed.descricao && parsed.descricao.length > agrupados[chave].descricao.length) {
                agrupados[chave].descricao = parsed.descricao;
            }
            const qtd = parseFloat(s.quantidade) || 0;
            agrupados[chave].quantidade += qtd;

            if (s._atestado_id && atestadosMap) {
                const atestado = atestadosMap.get(s._atestado_id);
                if (atestado) {
                    const existente = agrupados[chave].atestados.find(a => a.id === s._atestado_id);
                    if (existente) {
                        existente.quantidade += qtd;
                    } else {
                        agrupados[chave].atestados.push({
                            id: s._atestado_id,
                            contratante: atestado.contratante || 'N/A',
                            data_emissao: atestado.data_emissao,
                            quantidade: qtd
                        });
                    }
                }
            }
        });
        return Object.values(agrupados).sort((a, b) => a.descricao.localeCompare(b.descricao));
    },

    // === RELATORIOS ===

    async verResultadoConsolidado(id) {
        try {
            const atestado = await api.get(`/atestados/${id}`);
            const content = document.getElementById('resultadoContent');
            const servicos = atestado.servicos_json || [];
            const servicosConsolidados = this.agruparServicosPorDescricao(servicos);

            // Armazenar cache para filtro
            this.resultadoAtestadoCache = { atestado, servicosConsolidados };

            content.innerHTML = this.gerarRelatorioAtestado(atestado, servicosConsolidados);
            abrirModal('modalResultado');
        } catch (error) {
            ui.showAlert('Erro ao carregar resultado', 'error');
        }
    },

    filtrarServicosResultado(texto) {
        if (!this.resultadoAtestadoCache) return;

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
            const total = this.resultadoAtestadoCache.servicosConsolidados.length;
            contador.textContent = filtro ? `${visiveisCount} de ${total}` : `${total}`;
        }
    },

    gerarRelatorioAtestado(atestado, servicosConsolidados) {
        const servicos = atestado.servicos_json || [];
        if (!servicosConsolidados) {
            servicosConsolidados = this.agruparServicosPorDescricao(servicos);
        }

        return `
            <div class="relatorio-header">
                <h3>${atestado.descricao_servico || 'Atestado de Capacidade Tecnica'}</h3>
                <div class="relatorio-info">
                    ${atestado.contratante ? `
                        <div class="relatorio-info-item">
                            <span class="relatorio-info-label">Contratante</span>
                            <span class="relatorio-info-value">${atestado.contratante}</span>
                        </div>
                    ` : ''}
                    ${atestado.data_emissao ? `
                        <div class="relatorio-info-item">
                            <span class="relatorio-info-label">Data de Emissao</span>
                            <span class="relatorio-info-value">${this.formatarDataSemHora(atestado.data_emissao)}</span>
                        </div>
                    ` : ''}
                    <div class="relatorio-info-item">
                        <span class="relatorio-info-label">Itens Originais</span>
                        <span class="relatorio-info-value">${servicos.length}</span>
                    </div>
                    <div class="relatorio-info-item">
                        <span class="relatorio-info-label">Itens Consolidados</span>
                        <span class="relatorio-info-value" id="servicosResultadoCount">${servicosConsolidados.length}</span>
                    </div>
                </div>
            </div>

            <div class="relatorio-section">
                ${servicosConsolidados.length > 0 ? `
                    <div class="filtro-servicos">
                        <input type="text"
                               id="filtroResultadoInput"
                               class="form-input"
                               placeholder="Filtrar por descricao do servico..."
                               oninput="AtestadosModule.filtrarServicosResultado(this.value)">
                    </div>
                ` : ''}
                <h4 class="relatorio-section-title">Servicos Consolidados (agrupados por descricao)</h4>
                ${servicosConsolidados.length > 0 ? `
                    <table class="relatorio-table">
                        <thead>
                            <tr>
                                <th style="width: 40px;">#</th>
                                <th>Descricao do Servico</th>
                                <th style="width: 80px;">Unidade</th>
                                <th style="width: 120px;">Quantidade Total</th>
                            </tr>
                        </thead>
                        <tbody id="tabelaServicosResultado">
                            ${servicosConsolidados.map((s, i) => `
                                <tr data-servico-idx="${i}">
                                    <td>${i + 1}</td>
                                    <td>${s.descricao}</td>
                                    <td>${s.unidade}</td>
                                    <td class="numero">${formatarNumero(s.quantidade)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                ` : '<p class="text-muted">Nenhum servico detalhado foi extraido deste documento.</p>'}
            </div>
        `;
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

            const servicosConsolidados = this.agruparServicosPorDescricao(todosServicos, atestadosMap);

            this.relatorioConsolidadoCache = {
                atestados: todosAtestados,
                totalServicos: totalServicos,
                servicosConsolidados: servicosConsolidados
            };

            content.innerHTML = this.gerarRelatorioGeral(this.relatorioConsolidadoCache);

        } catch (error) {
            content.innerHTML = `<div class="alert alert-danger">Erro ao carregar atestados: ${error.message}</div>`;
        }
    },

    filtrarServicosConsolidados(texto) {
        if (!this.relatorioConsolidadoCache) return;

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
            const total = this.relatorioConsolidadoCache.servicosConsolidados.length;
            contador.textContent = filtro ? `${visiveisCount} de ${total}` : `${total}`;
        }
    },

    mostrarDetalhesServico(idx) {
        if (!this.relatorioConsolidadoCache) return;

        const servico = this.relatorioConsolidadoCache.servicosConsolidados[idx];
        if (!servico) return;

        const content = document.getElementById('detalhesServicoContent');
        const atestadosOrdenados = [...servico.atestados].sort((a, b) => b.quantidade - a.quantidade);

        content.innerHTML = `
            <div class="detalhes-servico-header">
                <h4>${servico.descricao}</h4>
                <div class="detalhes-servico-info">
                    <span class="badge badge-primary">${servico.unidade}</span>
                    <span class="badge badge-success">Total: ${formatarNumero(servico.quantidade)}</span>
                    <span class="badge badge-info">${servico.atestados.length} atestado(s)</span>
                </div>
            </div>
            <table class="relatorio-table">
                <thead>
                    <tr>
                        <th style="width: 40px;">#</th>
                        <th>Contratante</th>
                        <th style="width: 120px;">Data Emissao</th>
                        <th style="width: 120px;">Quantidade</th>
                        <th style="width: 80px;">%</th>
                    </tr>
                </thead>
                <tbody>
                    ${atestadosOrdenados.map((a, i) => {
                        const percentual = servico.quantidade > 0 ? (a.quantidade / servico.quantidade * 100) : 0;
                        return `
                            <tr class="clickable-row" onclick="AtestadosModule.verAtestado(${a.id})">
                                <td>${i + 1}</td>
                                <td>${a.contratante}</td>
                                <td>${a.data_emissao ? this.formatarDataSemHora(a.data_emissao) : 'N/A'}</td>
                                <td class="numero">${formatarNumero(a.quantidade)}</td>
                                <td class="numero">${percentual.toFixed(1)}%</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
            <p class="text-muted mt-2" style="font-size: 0.85em;">Clique em uma linha para ver o atestado completo.</p>
        `;

        abrirModal('modalDetalhesServico');
    },

    verAtestado(id) {
        fecharModal('modalDetalhesServico');
        fecharModal('modalRelatorioGeral');
        this.verResultadoConsolidado(id);
    },

    gerarRelatorioGeral(dados) {
        const { atestados, totalServicos, servicosConsolidados } = dados;

        return `
            <div class="relatorio-header">
                <h3>Consolidado de Todos os Atestados</h3>
                <div class="relatorio-info">
                    <div class="relatorio-info-item">
                        <span class="relatorio-info-label">Total de Atestados</span>
                        <span class="relatorio-info-value">${atestados.length}</span>
                    </div>
                    <div class="relatorio-info-item">
                        <span class="relatorio-info-label">Itens Originais</span>
                        <span class="relatorio-info-value">${totalServicos}</span>
                    </div>
                    <div class="relatorio-info-item">
                        <span class="relatorio-info-label">Itens Consolidados</span>
                        <span class="relatorio-info-value" id="servicosFiltradosCount">${servicosConsolidados.length}</span>
                    </div>
                </div>
            </div>

            <div class="relatorio-section">
                <div class="filtro-servicos">
                    <input type="text"
                           id="filtroServicosInput"
                           class="form-input"
                           placeholder="Filtrar por descricao do servico..."
                           oninput="AtestadosModule.filtrarServicosConsolidados(this.value)">
                </div>
                <h4 class="relatorio-section-title">Servicos Consolidados de Todos os Atestados</h4>
                <p class="text-muted" style="font-size: 0.85em; margin-bottom: 10px;">Clique em um servico para ver quais atestados compoem o total.</p>
                ${servicosConsolidados.length > 0 ? `
                    <table class="relatorio-table">
                        <thead>
                            <tr>
                                <th style="width: 40px;">#</th>
                                <th>Descricao do Servico</th>
                                <th style="width: 80px;">Unidade</th>
                                <th style="width: 120px;">Quantidade Total</th>
                                <th style="width: 80px;">Atestados</th>
                            </tr>
                        </thead>
                        <tbody id="tabelaServicosConsolidados">
                            ${servicosConsolidados.map((s, i) => `
                                <tr class="clickable-row" data-servico-idx="${i}" onclick="AtestadosModule.mostrarDetalhesServico(${i})">
                                    <td>${i + 1}</td>
                                    <td>${s.descricao}</td>
                                    <td>${s.unidade}</td>
                                    <td class="numero">${formatarNumero(s.quantidade)}</td>
                                    <td class="numero">${s.atestados.length}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                ` : '<p class="text-muted">Nenhum servico encontrado.</p>'}
            </div>
        `;
    }
};

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => AtestadosModule.init());
