// LicitaFacil - Utilitario de Sanitizacao
// Previne vulnerabilidades XSS ao escapar caracteres HTML perigosos

const Sanitize = {
    /**
     * Escapa caracteres HTML perigosos para prevenir XSS
     * @param {string|any} text - Texto a ser sanitizado
     * @returns {string} - Texto seguro para uso em innerHTML
     */
    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    },

    /**
     * Escapa caracteres para uso em atributos HTML
     * @param {string|any} text - Texto a ser sanitizado
     * @returns {string} - Texto seguro para uso em atributos
     */
    escapeAttribute(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    },

    /**
     * Escapa texto para uso seguro em contexto JavaScript (onclick, etc)
     * @param {string|any} text - Texto a ser sanitizado
     * @returns {string} - Texto seguro para uso em JS inline
     */
    escapeJs(text) {
        if (text === null || text === undefined) return '';
        return String(text)
            .replace(/\\/g, '\\\\')
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"')
            .replace(/\n/g, '\\n')
            .replace(/\r/g, '\\r');
    }
};

// Expor globalmente
window.Sanitize = Sanitize;
