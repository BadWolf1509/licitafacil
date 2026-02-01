// LicitaFacil - Modulo de Atestados - Status de Jobs
// Funcoes para determinar e formatar status de jobs

import { parseJobTime } from './formatters.js';

// Cache de pipeline por job
const lastKnownPipeline = new Map();

export function getJobStatusLabel(status) {
    const labels = {
        pending: 'Na fila',
        processing: 'Processando',
        failed: 'Falhou',
        cancelled: 'Cancelado',
        completed: 'Concluido'
    };
    return labels[status] || 'Processando';
}

export function getPipelineFromStage(stage) {
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
}

export function getEffectivePipeline(job) {
    if (job.pipeline) {
        lastKnownPipeline.set(job.id, job.pipeline);
        return job.pipeline;
    }
    const currentPipeline = getPipelineFromStage(job.progress_stage);
    if (currentPipeline) {
        lastKnownPipeline.set(job.id, currentPipeline);
        return currentPipeline;
    }
    return lastKnownPipeline.get(job.id) || null;
}

export function clearPipelineCache(jobId) {
    lastKnownPipeline.delete(jobId);
}

export function getPipelineLabel(pipeline) {
    const labels = {
        'NATIVE_TEXT': 'Extracao Nativa',
        'LOCAL_OCR': 'OCR Local',
        'CLOUD_OCR': 'OCR Cloud (Azure)',
        'VISION_AI': 'GPT-4o Vision'
    };
    return labels[pipeline] || pipeline;
}

export function normalizeJobStage(stage, status) {
    const normalized = (stage || '').toString().toLowerCase();
    if (!normalized || normalized === 'pending' || normalized === 'queued') {
        return status === 'pending' ? 'queued' : 'processing';
    }
    if (normalized === 'finalizar' || normalized === 'finalizando') {
        return 'final';
    }
    return normalized;
}

export function getDisplayStatus(job) {
    const raw = (job?.status || '').toString().toLowerCase();
    if (raw === 'failed' || raw === 'cancelled' || raw === 'completed') {
        return raw;
    }
    const stage = normalizeJobStage(job?.progress_stage, raw);
    const hasStarted = Boolean(job?.started_at);
    const hasProgress = Number(job?.progress_current) > 0 || Number(job?.progress_total) > 0;
    if (raw === 'pending' && (hasStarted || hasProgress || stage !== 'queued')) {
        return 'processing';
    }
    if (!raw || raw === 'queued') {
        return 'pending';
    }
    return raw;
}

export function getJobStageLabel(stage, status) {
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
}

export function getJobProgress(job) {
    const total = Number(job.progress_total) || 0;
    const current = Number(job.progress_current) || 0;
    const percent = total > 0 ? Math.min(100, Math.round((current / total) * 100)) : 0;
    const displayStatus = getDisplayStatus(job);
    const stage = normalizeJobStage(job.progress_stage, displayStatus);
    const stageLabel = getJobStageLabel(stage, displayStatus);
    const message = job.progress_message || stageLabel;
    return { total, current, percent, stage, stageLabel, message, displayStatus };
}

export function getJobFileName(job) {
    if (job.original_filename) return job.original_filename;
    if (!job.file_path) return 'arquivo';
    const parts = job.file_path.split(/[\\/]/);
    return parts[parts.length - 1] || 'arquivo';
}

export function formatJobError(job) {
    if (!job || !job.error) return '';
    const raw = String(job.error);
    const lines = raw.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    if (!lines.length) return '';
    const errorLine = [...lines].reverse().find(line => /error|exception|falha/i.test(line))
        || lines[lines.length - 1];
    const cleaned = errorLine.replace(/^erro\s*:?\s*/i, '').trim();
    if (!cleaned) return '';
    return cleaned.length > 180 ? `${cleaned.slice(0, 177)}...` : cleaned;
}

export function getJobTimes(job) {
    const createdAt = parseJobTime(job.created_at);
    const localCreatedAt = parseJobTime(job.local_created_at);
    let startedAt = parseJobTime(job.started_at);
    const endedAt = parseJobTime(job.completed_at || job.canceled_at);
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

    const displayStatus = getDisplayStatus(job);
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
}

export function getJobStateHash(job) {
    const progress = getJobProgress(job);
    const times = getJobTimes(job);
    return JSON.stringify({
        status: getDisplayStatus(job),
        progress: progress.percent,
        stage: progress.stage,
        message: progress.message,
        error: job.error,
        poll_error: job.poll_error,
        queueMs: Math.floor(times.queueMs / 1000),
        processingMs: Math.floor(times.processingMs / 1000)
    });
}
