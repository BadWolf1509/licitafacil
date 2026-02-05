// LicitaFacil - Modulo de Atestados - Relatorios
// Funcoes para geracao de relatorios consolidados

import { formatarDataSemHora } from './formatters.js';
import { agruparServicosPorDescricao } from './sorting.js';

// Funcao global para formatacao de numeros (espera-se que exista no escopo global)
const formatarNumero = (num) => {
    if (typeof window !== 'undefined' && window.formatarNumero) {
        return window.formatarNumero(num);
    }
    return new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(num || 0);
};

export function gerarRelatorioAtestado(atestado, servicosConsolidados) {
    const servicos = atestado.servicos_json || [];
    if (!servicosConsolidados) {
        servicosConsolidados = agruparServicosPorDescricao(servicos);
    }

    return `
        <div class="relatorio-header">
            <h3>${Sanitize.escapeHtml(atestado.descricao_servico || 'Atestado de Capacidade Tecnica')}</h3>
            <div class="relatorio-info">
                ${atestado.contratante ? `
                    <div class="relatorio-info-item">
                        <span class="relatorio-info-label">Contratante</span>
                        <span class="relatorio-info-value">${Sanitize.escapeHtml(atestado.contratante)}</span>
                    </div>
                ` : ''}
                ${atestado.data_emissao ? `
                    <div class="relatorio-info-item">
                        <span class="relatorio-info-label">Data de Emissao</span>
                        <span class="relatorio-info-value">${formatarDataSemHora(atestado.data_emissao)}</span>
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
}

export function gerarRelatorioGeral(dados) {
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

export function gerarDetalhesServico(servico, formatarDataFn = formatarDataSemHora) {
    const atestadosOrdenados = [...servico.atestados].sort((a, b) => b.quantidade - a.quantidade);

    return `
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
                            <td>${Sanitize.escapeHtml(a.contratante || '')}</td>
                            <td>${a.data_emissao ? formatarDataFn(a.data_emissao) : 'N/A'}</td>
                            <td class="numero">${formatarNumero(a.quantidade)}</td>
                            <td class="numero">${percentual.toFixed(1)}%</td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
        <p class="text-muted mt-2" style="font-size: 0.85em;">Clique em uma linha para ver o atestado completo.</p>
    `;
}
