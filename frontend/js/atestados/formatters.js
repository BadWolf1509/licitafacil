// LicitaFacil - Modulo de Atestados - Formatadores
// Funcoes de formatacao de tempo, data e unidades

export function formatarTempo(ms) {
    const total = Math.max(0, Math.floor(ms / 1000));
    const min = Math.floor(total / 60);
    const sec = total % 60;
    return `${min}m ${sec.toString().padStart(2, '0')}s`;
}

export function formatarDataSemHora(dataStr) {
    if (!dataStr) return '';
    const data = new Date(dataStr);
    return data.toLocaleDateString('pt-BR');
}

export function parseJobTime(value) {
    if (!value) return null;
    const time = Date.parse(value);
    return Number.isNaN(time) ? null : time;
}

export function normalizarUnidade(unidade) {
    return (unidade || '')
        .toString()
        .toUpperCase()
        .replace(/\u00b2/g, '2')
        .replace(/\u00b3/g, '3')
        .replace('M^2', 'M2')
        .replace('M^3', 'M3')
        .replace(/\s+/g, '');
}

export function normalizarDescricaoParaAgrupamento(descricao) {
    return (descricao || '')
        .toString()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toUpperCase()
        .replace(/[^A-Z0-9]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}
