// LicitaFacil - Supabase Realtime Module
// Substitui polling por WebSocket para atualizacoes de jobs em tempo real

/**
 * Estado do modulo Realtime
 */
const realtimeState = {
    channel: null,
    subscriptions: new Map(), // jobId -> callback
    isConnected: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 1000
};

/**
 * Verifica se Realtime esta disponivel
 * Requer que o usuario esteja autenticado via Supabase Auth (nao legacy JWT)
 * @returns {Promise<boolean>}
 */
async function isRealtimeAvailable() {
    // Verificar se Supabase esta inicializado
    if (typeof isSupabaseAvailable !== 'function' || !isSupabaseAvailable()) {
        return false;
    }

    if (typeof getSupabaseClient !== 'function') {
        return false;
    }

    const client = getSupabaseClient();
    if (!client) {
        return false;
    }

    // IMPORTANTE: Verificar se ha sessao Supabase autenticada
    // Realtime com RLS requer autenticacao Supabase, nao funciona com JWT legado
    try {
        const { data: { session } } = await client.auth.getSession();
        if (!session) {
            // Usuario logado via JWT legado, Realtime nao vai funcionar
            return false;
        }
        return true;
    } catch (error) {
        console.warn('[REALTIME] Error checking Supabase session:', error);
        return false;
    }
}

/**
 * Inicializa o canal Realtime para jobs
 * @returns {Promise<boolean>} - true se conectado com sucesso
 */
async function initRealtimeChannel() {
    const available = await isRealtimeAvailable();
    if (!available) {
        // Nao logar como erro - e esperado quando usuario usa auth legado
        console.log('[REALTIME] Supabase Auth session not available, using polling fallback');
        return false;
    }

    if (realtimeState.channel) {
        console.log('[REALTIME] Channel already initialized');
        return realtimeState.isConnected;
    }

    try {
        const client = getSupabaseClient();

        realtimeState.channel = client
            .channel('processing-jobs-changes')
            .on(
                'postgres_changes',
                {
                    event: '*', // INSERT, UPDATE, DELETE
                    schema: 'public',
                    table: 'processing_jobs'
                },
                (payload) => {
                    handleJobChange(payload);
                }
            )
            .subscribe((status) => {
                console.log('[REALTIME] Subscription status:', status);
                if (status === 'SUBSCRIBED') {
                    realtimeState.isConnected = true;
                    realtimeState.reconnectAttempts = 0;
                    console.log('[REALTIME] Connected to processing_jobs channel');
                } else if (status === 'CLOSED' || status === 'CHANNEL_ERROR') {
                    realtimeState.isConnected = false;
                    attemptReconnect();
                }
            });

        return true;
    } catch (error) {
        console.error('[REALTIME] Failed to initialize channel:', error);
        return false;
    }
}

/**
 * Tenta reconectar ao canal
 */
async function attemptReconnect() {
    if (realtimeState.reconnectAttempts >= realtimeState.maxReconnectAttempts) {
        console.log('[REALTIME] Max reconnect attempts reached, falling back to polling');
        return;
    }

    realtimeState.reconnectAttempts++;
    const delay = realtimeState.reconnectDelay * Math.pow(2, realtimeState.reconnectAttempts - 1);

    console.log(`[REALTIME] Reconnecting in ${delay}ms (attempt ${realtimeState.reconnectAttempts})`);

    setTimeout(async () => {
        if (realtimeState.channel) {
            realtimeState.channel.unsubscribe();
            realtimeState.channel = null;
        }
        await initRealtimeChannel();
    }, delay);
}

/**
 * Processa mudanca de job recebida via Realtime
 * @param {object} payload - Payload do Supabase Realtime
 */
function handleJobChange(payload) {
    const { eventType, new: newRecord, old: oldRecord } = payload;

    console.log('[REALTIME] Job change:', eventType, newRecord?.id || oldRecord?.id);

    // Determinar o job afetado
    const job = newRecord || oldRecord;
    if (!job || !job.id) return;

    // Notificar todos os callbacks registrados para este job
    const callback = realtimeState.subscriptions.get(job.id);
    if (callback) {
        callback({
            eventType,
            job: newRecord,
            oldJob: oldRecord
        });
    }

    // Notificar callback global (para atualizacoes de lista)
    const globalCallback = realtimeState.subscriptions.get('*');
    if (globalCallback) {
        globalCallback({
            eventType,
            job: newRecord,
            oldJob: oldRecord
        });
    }
}

/**
 * Registra callback para mudancas de um job especifico
 * @param {string} jobId - ID do job (ou '*' para todos)
 * @param {function} callback - Funcao a ser chamada quando job mudar
 * @returns {Promise<function>} - Funcao para cancelar a subscription
 */
async function subscribeToJob(jobId, callback) {
    // Inicializar canal se necessario
    if (!realtimeState.channel) {
        await initRealtimeChannel();
    }

    realtimeState.subscriptions.set(jobId, callback);

    // Retornar funcao para cancelar
    return () => {
        realtimeState.subscriptions.delete(jobId);
    };
}

/**
 * Remove subscription de um job
 * @param {string} jobId - ID do job
 */
function unsubscribeFromJob(jobId) {
    realtimeState.subscriptions.delete(jobId);
}

/**
 * Desconecta do canal Realtime
 */
function disconnectRealtime() {
    if (realtimeState.channel) {
        realtimeState.channel.unsubscribe();
        realtimeState.channel = null;
    }
    realtimeState.subscriptions.clear();
    realtimeState.isConnected = false;
    console.log('[REALTIME] Disconnected');
}

/**
 * Verifica se esta conectado ao Realtime
 * @returns {boolean}
 */
function isRealtimeConnected() {
    return realtimeState.isConnected;
}

/**
 * Retorna estatisticas do Realtime
 * @returns {object}
 */
function getRealtimeStats() {
    return {
        isConnected: realtimeState.isConnected,
        subscriptionsCount: realtimeState.subscriptions.size,
        reconnectAttempts: realtimeState.reconnectAttempts
    };
}

// Expor globalmente
if (typeof window !== 'undefined') {
    window.RealtimeModule = {
        init: initRealtimeChannel,
        isAvailable: isRealtimeAvailable,
        isConnected: isRealtimeConnected,
        subscribe: subscribeToJob,
        unsubscribe: unsubscribeFromJob,
        disconnect: disconnectRealtime,
        getStats: getRealtimeStats
    };
}

// Auto-inicializar quando config estiver carregado
document.addEventListener('DOMContentLoaded', () => {
    // Aguardar config carregar e entao inicializar
    const checkAndInit = async () => {
        const available = await isRealtimeAvailable();
        if (available) {
            console.log('[REALTIME] Initializing...');
            await initRealtimeChannel();
        } else {
            // Nao tentar reconectar infinitamente - usuario pode estar usando auth legado
            console.log('[REALTIME] Supabase Auth not available, polling will be used as fallback');
        }
    };

    // Aguardar um pouco para o auth config carregar
    setTimeout(checkAndInit, CONFIG.TIMEOUTS.REALTIME_RECONNECT);
});
