// LicitaFacil - Modulo de Atestados - Ordenacao e Parsing
// Funcoes para parsing de itens e ordenacao de servicos

import { normalizarUnidade, normalizarDescricaoParaAgrupamento } from './formatters.js';

export function extrairItemDescricao(servico) {
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
}

export function parseItemSortKey(item) {
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
}

export function compararItens(a, b) {
    const itemA = (extrairItemDescricao(a).item || '').toString();
    const itemB = (extrairItemDescricao(b).item || '').toString();

    if (!itemA && !itemB) return 0;
    if (!itemA) return 1;
    if (!itemB) return -1;

    const keyA = parseItemSortKey(itemA);
    const keyB = parseItemSortKey(itemB);

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
}

export function ordenarServicosPorItem(servicos) {
    return [...servicos].sort((a, b) => compararItens(a, b));
}

export function agruparServicosPorDescricao(servicos, atestadosMap = null) {
    const agrupados = {};
    servicos.forEach(s => {
        const parsed = extrairItemDescricao(s);
        const unidade = normalizarUnidade(s.unidade);
        const descricaoKey = normalizarDescricaoParaAgrupamento(parsed.descricao);
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
}
