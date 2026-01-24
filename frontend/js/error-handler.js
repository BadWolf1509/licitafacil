// LicitaFacil - Error Handler
// Centraliza tratamento de erros para operacoes assincronas

const ErrorHandler = {
    /**
     * Wrapper para operacoes assincronas com tratamento de erro
     * Exibe alerta e re-lanca o erro
     * @param {Function} asyncFn - Funcao assincrona a executar
     * @param {string} errorMessage - Mensagem de erro padrao
     * @returns {Promise} Resultado da funcao ou erro
     */
    async wrap(asyncFn, errorMessage = 'Erro na operacao') {
        try {
            return await asyncFn();
        } catch (error) {
            console.error(errorMessage, error);
            ui.showAlert(error.message || errorMessage, 'error');
            throw error;
        }
    },

    /**
     * Wrapper silencioso - nao re-lanca o erro
     * Retorna null em caso de erro
     * @param {Function} asyncFn - Funcao assincrona a executar
     * @param {string} errorMessage - Mensagem de erro padrao
     * @returns {Promise} Resultado da funcao ou null
     */
    async silent(asyncFn, errorMessage = 'Erro na operacao') {
        try {
            return await asyncFn();
        } catch (error) {
            console.error(errorMessage, error);
            ui.showAlert(error.message || errorMessage, 'error');
            return null;
        }
    },

    /**
     * Wrapper com callback de erro customizado
     * @param {Function} asyncFn - Funcao assincrona a executar
     * @param {Function} onError - Callback de erro (recebe error)
     * @returns {Promise} Resultado da funcao ou resultado do callback
     */
    async withCallback(asyncFn, onError) {
        try {
            return await asyncFn();
        } catch (error) {
            console.error('Operacao falhou:', error);
            if (onError) {
                return onError(error);
            }
            return null;
        }
    },

    /**
     * Wrapper com retry automatico
     * @param {Function} asyncFn - Funcao assincrona a executar
     * @param {number} maxRetries - Numero maximo de tentativas
     * @param {number} delayMs - Delay entre tentativas em ms
     * @returns {Promise} Resultado da funcao
     */
    async withRetry(asyncFn, maxRetries = 3, delayMs = 1000) {
        let lastError;
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                return await asyncFn();
            } catch (error) {
                lastError = error;
                console.warn(`Tentativa ${attempt}/${maxRetries} falhou:`, error.message);
                if (attempt < maxRetries) {
                    await new Promise(resolve => setTimeout(resolve, delayMs));
                }
            }
        }
        ui.showAlert(lastError.message || 'Operacao falhou apos multiplas tentativas', 'error');
        throw lastError;
    },

    /**
     * Wrapper com loading indicator
     * @param {Function} asyncFn - Funcao assincrona a executar
     * @param {string} loadingMessage - Mensagem durante carregamento
     * @param {string} errorMessage - Mensagem de erro
     * @returns {Promise} Resultado da funcao
     */
    async withLoading(asyncFn, loadingMessage = 'Carregando...', errorMessage = 'Erro na operacao') {
        ui.showAlert(loadingMessage, 'info');
        try {
            const result = await asyncFn();
            return result;
        } catch (error) {
            console.error(errorMessage, error);
            ui.showAlert(error.message || errorMessage, 'error');
            throw error;
        }
    },

    /**
     * Formata mensagem de erro da API
     * @param {Error|Object} error - Erro capturado
     * @returns {string} Mensagem formatada
     */
    formatApiError(error) {
        if (error?.detail) {
            return error.detail;
        }
        if (error?.message) {
            return error.message;
        }
        if (typeof error === 'string') {
            return error;
        }
        return 'Erro desconhecido';
    }
};

// Exportar para uso global
window.ErrorHandler = ErrorHandler;
