// LicitaFacil - Modulo de Atestados - Renderizacao de Jobs
// Funcoes para renderizar jobs de processamento

import { formatarTempo } from './formatters.js';
import {
    getDisplayStatus,
    getJobStatusLabel,
    getJobProgress,
    getJobTimes,
    getEffectivePipeline,
    getPipelineLabel,
    formatJobError,
    getJobFileName,
    getJobStateHash
} from './job-status.js';

export function renderProgressBar(job) {
    const progress = getJobProgress(job);
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
}

export function renderJobHtml(job, moduleName = 'AtestadosModule') {
    const displayStatus = getDisplayStatus(job);
    const statusLabel = getJobStatusLabel(displayStatus);
    const progress = getJobProgress(job);
    const progressText = progress.total > 0 ? `${progress.current}/${progress.total} (${progress.percent}%)` : '';
    const times = getJobTimes(job);

    const queueTimeText = displayStatus === 'pending' && times.hasQueue
        ? `Fila: ${formatarTempo(times.queueMs)}`
        : '';

    const processingTimeText = displayStatus === 'processing'
        ? `Tempo: ${formatarTempo(times.processingMs)}`
        : '';

    const pipeline = getEffectivePipeline(job);
    const pipelineText = displayStatus === 'processing' && pipeline
        ? `Pipeline: ${getPipelineLabel(pipeline)}`
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

    const fileName = getJobFileName(job);
    const syncError = job.poll_error ? `<div class="processing-job-error">${job.poll_error}</div>` : '';
    const errorMessage = formatJobError(job);
    const errorHtml = displayStatus === 'failed' && errorMessage
        ? `<div class="processing-job-error">${errorMessage}</div>`
        : '';
    const actionHtml = displayStatus === 'failed' || displayStatus === 'cancelled'
        ? `
            <button class="btn btn-outline btn-sm" onclick="${moduleName}.reprocessarJob('${job.id}')">Tentar novamente</button>
            <button class="btn btn-outline btn-sm" onclick="${moduleName}.excluirJob('${job.id}')">Remover</button>
        `
        : `<button class="btn btn-outline btn-sm" onclick="${moduleName}.cancelarJob('${job.id}')">Cancelar</button>`;

    return `
        <div class="processing-job-info">
            <div class="processing-job-head">
                <div class="processing-job-title" title="${fileName}">${fileName}</div>
                <span class="job-status ${displayStatus}">${statusLabel}</span>
            </div>
            <div class="processing-job-meta">
                ${metaItems}
            </div>
            ${renderProgressBar(job)}
            ${syncError}
            ${errorHtml}
        </div>
        <div class="processing-job-actions">
            ${actionHtml}
        </div>
    `;
}

export function updateJobElement(job) {
    const jobElement = document.querySelector(`[data-job-id="${job.id}"]`);
    if (!jobElement) return false;

    const displayStatus = getDisplayStatus(job);
    jobElement.className = `processing-job ${displayStatus}`;
    jobElement.innerHTML = renderJobHtml(job);
    return true;
}

export function renderProcessingJobsList(jobs, lastRenderedJobs, moduleName = 'AtestadosModule') {
    const container = document.getElementById('processingJobs');
    if (!container) return { updated: false };

    if (jobs.length === 0) {
        if (container.innerHTML !== '') {
            container.innerHTML = '';
            lastRenderedJobs.clear();
        }
        return { updated: true, fullRebuild: false };
    }

    const currentJobIds = new Set(jobs.map(j => j.id));
    const renderedJobIds = new Set(lastRenderedJobs.keys());
    const needsFullRebuild =
        currentJobIds.size !== renderedJobIds.size ||
        ![...currentJobIds].every(id => renderedJobIds.has(id)) ||
        !container.querySelector('.processing-job');

    if (needsFullRebuild) {
        const queuedCount = jobs.filter(job => getDisplayStatus(job) === 'pending').length;
        const processingCount = jobs.filter(job => getDisplayStatus(job) === 'processing').length;
        const attentionCount = jobs.filter(job => {
            const status = getDisplayStatus(job);
            return status === 'failed' || status === 'cancelled';
        }).length;
        const summaryParts = [];
        if (queuedCount > 0) summaryParts.push(`${queuedCount} na fila`);
        if (processingCount > 0) summaryParts.push(`${processingCount} processando`);
        if (attentionCount > 0) summaryParts.push(`${attentionCount} com atencao`);
        const summaryText = summaryParts.join(' | ');

        const jobsHtml = jobs.map(job => {
            const displayStatus = getDisplayStatus(job);
            return `
                <div class="processing-job ${displayStatus}" data-job-id="${job.id}">
                    ${renderJobHtml(job, moduleName)}
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

        lastRenderedJobs.clear();
        jobs.forEach(job => {
            lastRenderedJobs.set(job.id, getJobStateHash(job));
        });
        return { updated: true, fullRebuild: true };
    } else {
        let hasChanges = false;
        jobs.forEach(job => {
            const currentHash = getJobStateHash(job);
            const lastHash = lastRenderedJobs.get(job.id);

            if (currentHash !== lastHash) {
                updateJobElement(job);
                lastRenderedJobs.set(job.id, currentHash);
                hasChanges = true;
            }
        });

        if (hasChanges) {
            const summaryElement = container.querySelector('[data-summary]');
            if (summaryElement) {
                const queuedCount = jobs.filter(job => getDisplayStatus(job) === 'pending').length;
                const processingCount = jobs.filter(job => getDisplayStatus(job) === 'processing').length;
                const attentionCount = jobs.filter(job => {
                    const status = getDisplayStatus(job);
                    return status === 'failed' || status === 'cancelled';
                }).length;
                const summaryParts = [];
                if (queuedCount > 0) summaryParts.push(`${queuedCount} na fila`);
                if (processingCount > 0) summaryParts.push(`${processingCount} processando`);
                if (attentionCount > 0) summaryParts.push(`${attentionCount} com atencao`);
                summaryElement.textContent = summaryParts.join(' | ');
            }
        }
        return { updated: hasChanges, fullRebuild: false };
    }
}
