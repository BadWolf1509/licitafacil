// LicitaFacil - Modulo Encontrar Licitacoes
// Busca rica no PNCP com integração ao Calendário e Gestão de Licitações

const EncontrarModule = {
    // === ESTADO ===
    resultados: [],
    totalResultados: 0,
    paginaAtual: 1,
    pageSize: 20,
    viewMode: 'grade', // 'grade' | 'lista'
    tabAtiva: 'busca',

    // Item selecionado para gerenciar
    itemParaGerenciar: null,

    // === INICIALIZAÇÃO ===

    init() {
        this.setupEventDelegation();
        this.setupFiltros();
        this.setDefaultDates();
        this.carregarAlertas();
    },

    // === EVENT DELEGATION ===

    setupEventDelegation() {
        const self = this;

        document.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;
            const action = btn.dataset.action;

            switch (action) {
                case 'buscar':
                    self.buscar(1);
                    break;
                case 'switchTab':
                    self.switchTab(btn.dataset.tab);
                    break;
                case 'setView':
                    self.setView(btn.dataset.view);
                    break;
                case 'toggleFiltrosAvancados':
                    self.toggleFiltrosAvancados();
                    break;
                case 'limparFiltros':
                    self.limparFiltros();
                    break;
                case 'abrirGerenciar':
                    self.abrirGerenciar(btn.dataset.index);
                    break;
                case 'fecharModalGerenciar':
                    self.fecharModalGerenciar();
                    break;
                case 'confirmarGerenciar':
                    self.confirmarGerenciar();
                    break;
                case 'novoAlerta':
                    self.novoAlerta();
                    break;
                case 'fecharModalAlerta':
                    self.fecharModalAlerta();
                    break;
                case 'salvarAlerta':
                    self.salvarAlerta();
                    break;
                case 'editarAlerta':
                    self.editarAlerta(btn.dataset.id);
                    break;
                case 'excluirAlerta':
                    self.excluirAlerta(btn.dataset.id);
                    break;
                case 'toggleAlerta':
                    self.toggleAlerta(btn.dataset.id);
                    break;
                case 'paginaBusca':
                    self.buscar(parseInt(btn.dataset.page));
                    break;
            }
        });

        // Buscar ao pressionar Enter na barra de busca
        document.getElementById('searchKeywords')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') self.buscar(1);
        });

        // Toggle checkbox lembrete
        document.getElementById('gerenciarCriarLembrete')?.addEventListener('change', function () {
            const config = document.getElementById('lembreteConfig');
            if (config) config.classList.toggle('hidden', !this.checked);
        });
    },

    // === FILTROS ===

    setupFiltros() {
        // Não precisa de debounce aqui — busca é disparada via botão
    },

    setDefaultDates() {
        const hoje = new Date();
        const em30dias = new Date();
        em30dias.setDate(hoje.getDate() + 30);

        const fmt = (d) => d.toISOString().split('T')[0];

        const ini = document.getElementById('filterDataIni');
        const fim = document.getElementById('filterDataFim');
        if (ini) ini.value = fmt(hoje);
        if (fim) fim.value = fmt(em30dias);
    },

    toggleFiltrosAvancados() {
        const panel = document.getElementById('filtrosAvancados');
        const btn = document.querySelector('[data-action="toggleFiltrosAvancados"]');
        if (!panel) return;
        panel.classList.toggle('hidden');
        if (btn) btn.textContent = panel.classList.contains('hidden') ? '+ Mais filtros' : '− Menos filtros';
    },

    limparFiltros() {
        document.getElementById('searchKeywords').value = '';
        document.getElementById('filterUF').value = '';
        document.getElementById('filterModalidade').value = '';
        document.getElementById('filterValorMin').value = '';
        document.getElementById('filterValorMax').value = '';
        this.setDefaultDates();
        // Limpar resultados
        this.resultados = [];
        this.renderResultados([]);
        document.getElementById('resultadosToolbar')?.classList.add('hidden');
        document.getElementById('buscaPaginacao')?.classList.add('hidden');
        document.getElementById('emptyStateBusca')?.classList.remove('hidden');
        const badge = document.getElementById('buscaBadge');
        if (badge) badge.classList.add('hidden');
    },

    getParams() {
        const keywords = document.getElementById('searchKeywords')?.value.trim() || '';
        const uf = document.getElementById('filterUF')?.value || '';
        const modalidade = document.getElementById('filterModalidade')?.value || '';
        const valorMin = document.getElementById('filterValorMin')?.value || '';
        const valorMax = document.getElementById('filterValorMax')?.value || '';
        const dataIni = document.getElementById('filterDataIni')?.value || '';
        const dataFim = document.getElementById('filterDataFim')?.value || '';

        return { keywords, uf, modalidade, valorMin, valorMax, dataIni, dataFim };
    },

    // === BUSCA ===

    async buscar(pagina = 1) {
        this.paginaAtual = pagina;
        const params = this.getParams();

        // Montar query string para o endpoint
        const qs = new URLSearchParams();
        if (params.dataIni) qs.set('data_inicial', params.dataIni.replace(/-/g, ''));
        if (params.dataFim) qs.set('data_final', params.dataFim.replace(/-/g, ''));
        if (params.modalidade) qs.set('codigo_modalidade', params.modalidade);
        if (params.uf) qs.set('uf', params.uf);
        if (params.valorMin) qs.set('valor_minimo', params.valorMin);
        if (params.valorMax) qs.set('valor_maximo', params.valorMax);

        const container = document.getElementById('resultadosGrid');
        if (!container) return;

        // Loading state
        container.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';
        document.getElementById('resultadosToolbar')?.classList.add('hidden');
        document.getElementById('emptyStateBusca')?.classList.add('hidden');

        try {
            const response = await api.get(`/pncp/busca?${qs}`);
            let items = response.data || [];

            // Filtro client-side por keywords
            if (params.keywords) {
                const kw = params.keywords.toLowerCase();
                items = items.filter(item => {
                    const objeto = (item.objetoCompra || '').toLowerCase();
                    const orgao = (item.orgaoEntidade?.razaoSocial || '').toLowerCase();
                    return objeto.includes(kw) || orgao.includes(kw);
                });
            }

            // Paginação client-side (API retorna tudo de uma vez)
            const total = items.length;
            const inicio = (pagina - 1) * this.pageSize;
            const pagItems = items.slice(inicio, inicio + this.pageSize);
            const totalPaginas = Math.ceil(total / this.pageSize) || 1;

            this.resultados = items; // guarda todos para paginação
            this.renderResultados(pagItems);
            this.renderToolbar(total);
            this.renderPaginacao('buscaPaginacao', pagina, totalPaginas);

            // Badge na tab
            const badge = document.getElementById('buscaBadge');
            if (badge) {
                badge.textContent = total;
                badge.classList.toggle('hidden', total === 0);
            }
        } catch (err) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>Erro ao buscar no PNCP. Verifique sua conexão e tente novamente.</p>
                </div>`;
            console.error('Erro na busca PNCP:', err);
        }
    },

    // === RENDER CARDS ===

    renderResultados(items) {
        const container = document.getElementById('resultadosGrid');
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = `
                <div class="empty-state" id="emptyStateBusca">
                    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
                        <circle cx="28" cy="28" r="20"/><path d="M44 44l8 8"/>
                    </svg>
                    <h3>Nenhuma licitação encontrada</h3>
                    <p>Tente ampliar o período ou remover alguns filtros.</p>
                </div>`;
            return;
        }

        container.classList.toggle('view-lista', this.viewMode === 'lista');

        const agora = new Date();
        const limite48h = new Date(agora.getTime() - 48 * 60 * 60 * 1000);

        container.innerHTML = items.map((item, idx) => {
            const globalIdx = (this.paginaAtual - 1) * this.pageSize + idx;
            return this.renderCard(item, globalIdx, limite48h);
        }).join('');
    },

    renderCard(item, idx, limite48h) {
        const orgao = item.orgaoEntidade || {};
        const unidade = item.unidadeOrgao || {};
        const objeto = Sanitize.escapeHtml(item.objetoCompra || 'Sem descrição');
        const orgaoNome = Sanitize.escapeHtml(orgao.razaoSocial || 'Órgão não informado');
        const modalidade = Sanitize.escapeHtml(item.modalidadeNome || '');
        const uf = Sanitize.escapeHtml(unidade.ufSigla || '');
        const valor = item.valorTotalEstimado;
        const linkEdital = Sanitize.escapeHtml(item.linkSistemaOrigem || '#');

        // Badge "Novo"
        const dataPublicacao = item.dataPublicacao ? new Date(item.dataPublicacao) : null;
        const isNovo = dataPublicacao && dataPublicacao >= limite48h;

        // Formatação de data abertura
        let aberturaTexto = 'Data não informada';
        if (item.dataAberturaProposta) {
            const dt = new Date(item.dataAberturaProposta);
            aberturaTexto = dt.toLocaleString('pt-BR', {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
            });
        }

        // Formatação de valor
        let valorTexto = valor != null
            ? `R$ ${parseFloat(valor).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
            : 'Valor não estimado';

        // Classe da badge de modalidade
        const modalidadeLower = modalidade.toLowerCase();
        let modalidadeClass = '';
        if (modalidadeLower.includes('pregão')) modalidadeClass = 'pregao';
        else if (modalidadeLower.includes('concorrência')) modalidadeClass = 'concorrencia';
        else if (modalidadeLower.includes('dispensa') || modalidadeLower.includes('inexigibilidade')) modalidadeClass = 'dispensa';

        if (this.viewMode === 'lista') {
            return `
            <div class="licitacao-card card-lista">
                <div class="card-objeto">${objeto}</div>
                <div class="card-meta-item">${uf}</div>
                <div class="card-meta-item"><strong>${valorTexto}</strong></div>
                <div class="card-meta-item">⏱ ${aberturaTexto}</div>
                <div class="card-actions">
                    ${linkEdital !== '#' ? `<a href="${linkEdital}" target="_blank" rel="noopener noreferrer" class="card-btn-edital">Edital ↗</a>` : ''}
                    <button class="card-btn-gerenciar" data-action="abrirGerenciar" data-index="${idx}">→ Gerenciar</button>
                </div>
            </div>`;
        }

        return `
        <div class="licitacao-card">
            <div class="card-header">
                ${modalidade ? `<span class="card-badge-modalidade ${modalidadeClass}">${modalidade}</span>` : ''}
                ${uf ? `<span class="card-badge-uf">${uf}</span>` : ''}
                ${isNovo ? `<span class="card-badge-novo">Novo</span>` : ''}
            </div>
            <div class="card-objeto">${objeto}</div>
            <div class="card-orgao">${orgaoNome}${orgao.cnpj ? ` — CNPJ ${Sanitize.escapeHtml(orgao.cnpj)}` : ''}</div>
            <div class="card-valor">${valorTexto}</div>
            <div class="card-abertura">⏱ Abertura: <strong>${aberturaTexto}</strong></div>
            <div class="card-actions">
                ${linkEdital !== '#' ? `<a href="${linkEdital}" target="_blank" rel="noopener noreferrer" class="card-btn-edital">Ver Edital ↗</a>` : '<span></span>'}
                <button class="card-btn-gerenciar" data-action="abrirGerenciar" data-index="${idx}">→ Gerenciar</button>
            </div>
        </div>`;
    },

    renderToolbar(total) {
        const toolbar = document.getElementById('resultadosToolbar');
        const count = document.getElementById('resultadosCount');
        if (!toolbar || !count) return;
        toolbar.classList.remove('hidden');
        count.textContent = `${total.toLocaleString('pt-BR')} resultado${total !== 1 ? 's' : ''}`;
    },

    renderPaginacao(containerId, paginaAtual, totalPaginas) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (totalPaginas <= 1) {
            container.classList.add('hidden');
            return;
        }
        container.classList.remove('hidden');
        const paginas = [];
        paginas.push(`<button ${paginaAtual === 1 ? 'disabled' : ''} data-action="paginaBusca" data-page="${paginaAtual - 1}">‹</button>`);
        for (let i = 1; i <= totalPaginas; i++) {
            if (i === 1 || i === totalPaginas || Math.abs(i - paginaAtual) <= 2) {
                paginas.push(`<button class="${i === paginaAtual ? 'active' : ''}" data-action="paginaBusca" data-page="${i}">${i}</button>`);
            } else if (Math.abs(i - paginaAtual) === 3) {
                paginas.push(`<span style="padding:0 4px;color:var(--text-muted)">…</span>`);
            }
        }
        paginas.push(`<button ${paginaAtual === totalPaginas ? 'disabled' : ''} data-action="paginaBusca" data-page="${paginaAtual + 1}">›</button>`);
        container.innerHTML = paginas.join('');
    },

    // === TABS ===

    switchTab(tab) {
        this.tabAtiva = tab;
        document.querySelectorAll('.encontrar-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        document.getElementById('tabBusca').classList.toggle('hidden', tab !== 'busca');
        document.getElementById('tabAlertas').classList.toggle('hidden', tab !== 'alertas');

        if (tab === 'alertas') this.carregarAlertas();
    },

    // === VIEW MODE ===

    setView(mode) {
        this.viewMode = mode;
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === mode);
        });
        // Re-renderizar a página atual
        const inicio = (this.paginaAtual - 1) * this.pageSize;
        const pagItems = this.resultados.slice(inicio, inicio + this.pageSize);
        this.renderResultados(pagItems);
    },

    // === ALERTAS (Monitores PNCP existentes) ===

    async carregarAlertas() {
        const container = document.getElementById('alertasGrid');
        if (!container) return;

        await ErrorHandler.withErrorHandling(async () => {
            const response = await api.get('/pncp/monitoramentos?page_size=50');
            const monitores = response.items || [];
            this.renderAlertas(monitores);

            // Badge na tab
            const badge = document.getElementById('alertasBadge');
            if (badge && monitores.length > 0) {
                badge.textContent = monitores.length;
                badge.classList.remove('hidden');
            }
        }, 'Erro ao carregar alertas', { container: 'alertasGrid' });
    },

    renderAlertas(monitores) {
        const container = document.getElementById('alertasGrid');
        if (!container) return;

        if (!monitores || monitores.length === 0) {
            container.innerHTML = `
                <div class="empty-state" id="emptyStateAlertas">
                    <p>Nenhum alerta configurado.</p>
                    <p>Crie alertas para receber novas licitações automaticamente.</p>
                    <button class="btn btn-primary" data-action="novoAlerta">+ Criar primeiro alerta</button>
                </div>`;
            return;
        }

        container.innerHTML = monitores.map(m => {
            const criterios = [];
            if (m.palavras_chave?.length) criterios.push(`"${m.palavras_chave.slice(0, 3).join(', ')}"`);
            if (m.ufs?.length) criterios.push(m.ufs.join(', '));
            if (m.valor_minimo || m.valor_maximo) {
                const min = m.valor_minimo ? `R$ ${parseFloat(m.valor_minimo).toLocaleString('pt-BR')}` : '';
                const max = m.valor_maximo ? `R$ ${parseFloat(m.valor_maximo).toLocaleString('pt-BR')}` : '';
                criterios.push(min && max ? `${min}–${max}` : min || max);
            }

            return `
            <div class="alerta-card">
                <div class="alerta-icon">${m.ativo ? '🔔' : '🔕'}</div>
                <div class="alerta-info">
                    <div class="alerta-nome">${Sanitize.escapeHtml(m.nome)}</div>
                    <div class="alerta-criterios">${criterios.length ? criterios.join(' | ') : 'Sem critérios específicos'}</div>
                </div>
                ${!m.ativo ? '<span style="font-size:0.75rem;color:var(--text-muted)">Pausado</span>' : ''}
                <div class="alerta-actions">
                    <button class="btn btn-sm btn-ghost" data-action="editarAlerta" data-id="${m.id}" title="Editar">✏</button>
                    <button class="btn btn-sm btn-ghost" data-action="toggleAlerta" data-id="${m.id}" title="${m.ativo ? 'Pausar' : 'Ativar'}">${m.ativo ? '⏸' : '▶'}</button>
                    <button class="btn btn-sm btn-ghost" data-action="excluirAlerta" data-id="${m.id}" title="Excluir">🗑</button>
                </div>
            </div>`;
        }).join('');
    },

    // === MODAL NOVO/EDITAR ALERTA ===

    novoAlerta() {
        this._alertaEditId = null;
        document.getElementById('modalAlertaTitle').textContent = 'Novo Alerta';
        document.getElementById('alertaNome').value = '';
        document.getElementById('alertaPalavras').value = '';
        document.getElementById('alertaUFs').value = '';
        document.getElementById('alertaValMin').value = '';
        document.getElementById('alertaValMax').value = '';
        abrirModal('modalAlerta');
    },

    async editarAlerta(id) {
        this._alertaEditId = id;
        try {
            const monitor = await api.get(`/pncp/monitoramentos/${id}`);
            document.getElementById('modalAlertaTitle').textContent = 'Editar Alerta';
            document.getElementById('alertaNome').value = monitor.nome || '';
            document.getElementById('alertaPalavras').value = (monitor.palavras_chave || []).join(', ');
            document.getElementById('alertaUFs').value = (monitor.ufs || []).join(', ');
            document.getElementById('alertaValMin').value = monitor.valor_minimo || '';
            document.getElementById('alertaValMax').value = monitor.valor_maximo || '';
            abrirModal('modalAlerta');
        } catch (err) {
            ui.showToast('Erro ao carregar alerta', 'error');
        }
    },

    fecharModalAlerta() {
        fecharModal('modalAlerta');
    },

    async salvarAlerta() {
        const nome = document.getElementById('alertaNome')?.value.trim();
        if (!nome) {
            ui.showToast('Informe um nome para o alerta', 'error');
            return;
        }

        const palavrasStr = document.getElementById('alertaPalavras')?.value.trim();
        const ufsStr = document.getElementById('alertaUFs')?.value.trim();
        const valMin = document.getElementById('alertaValMin')?.value;
        const valMax = document.getElementById('alertaValMax')?.value;

        const payload = {
            nome,
            palavras_chave: palavrasStr ? palavrasStr.split(',').map(s => s.trim()).filter(Boolean) : null,
            ufs: ufsStr ? ufsStr.split(',').map(s => s.trim().toUpperCase()).filter(Boolean) : null,
            valor_minimo: valMin ? parseFloat(valMin) : null,
            valor_maximo: valMax ? parseFloat(valMax) : null,
        };

        try {
            if (this._alertaEditId) {
                await api.put(`/pncp/monitoramentos/${this._alertaEditId}`, payload);
                ui.showToast('Alerta atualizado com sucesso!', 'success');
            } else {
                await api.post('/pncp/monitoramentos', payload);
                ui.showToast('Alerta criado com sucesso!', 'success');
            }
            this.fecharModalAlerta();
            this.carregarAlertas();
        } catch (err) {
            ui.showToast('Erro ao salvar alerta', 'error');
        }
    },

    async toggleAlerta(id) {
        try {
            await api.patch(`/pncp/monitoramentos/${id}/toggle`);
            this.carregarAlertas();
        } catch (err) {
            ui.showToast('Erro ao alternar alerta', 'error');
        }
    },

    async excluirAlerta(id) {
        confirmAction('Excluir este alerta permanentemente?', async () => {
            try {
                await api.delete(`/pncp/monitoramentos/${id}`);
                ui.showToast('Alerta removido', 'success');
                this.carregarAlertas();
            } catch (err) {
                ui.showToast('Erro ao excluir alerta', 'error');
            }
        });
    },

    // === MODAL GERENCIAR ===

    abrirGerenciar(idxStr) {
        const idx = parseInt(idxStr, 10);
        const item = this.resultados[idx];
        if (!item) return;
        this.itemParaGerenciar = item;

        // Preencher info
        const orgao = item.orgaoEntidade || {};
        const infoEl = document.getElementById('gerenciarInfo');
        if (infoEl) {
            const objeto = Sanitize.escapeHtml(item.objetoCompra || 'Sem descrição');
            const orgaoNome = Sanitize.escapeHtml(orgao.razaoSocial || 'Não informado');
            const valor = item.valorTotalEstimado
                ? `R$ ${parseFloat(item.valorTotalEstimado).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                : 'Valor não estimado';
            const controle = Sanitize.escapeHtml(item.numeroControlePNCP || '');

            infoEl.innerHTML = `
                <strong>${objeto}</strong>
                ${orgaoNome}<br>
                ${valor}${controle ? ` &nbsp;·&nbsp; PNCP: ${controle}` : ''}
            `;
        }

        // Lembrete section
        const dataAbertura = item.dataAberturaProposta ? new Date(item.dataAberturaProposta) : null;
        const lembreteSection = document.getElementById('lembreteSection');
        const lembreteDataTexto = document.getElementById('lembreteDataTexto');

        if (dataAbertura && lembreteSection) {
            lembreteSection.classList.remove('hidden');
            const antecedencia = parseInt(document.getElementById('gerenciarAntecedencia')?.value || '24', 10);
            const dataLembrete = new Date(dataAbertura.getTime() - antecedencia * 60 * 60 * 1000);
            if (lembreteDataTexto) {
                lembreteDataTexto.textContent = `🗓 Lembrete: ${dataLembrete.toLocaleString('pt-BR', {
                    day: '2-digit', month: '2-digit', year: 'numeric',
                    hour: '2-digit', minute: '2-digit',
                })}`;
            }
        } else if (lembreteSection) {
            lembreteSection.classList.add('hidden');
        }

        // Reset status
        const statusEl = document.getElementById('gerenciarStatus');
        if (statusEl) statusEl.value = 'em_analise';

        document.getElementById('gerenciarObs').value = '';
        abrirModal('modalGerenciar');
    },

    fecharModalGerenciar() {
        fecharModal('modalGerenciar');
        this.itemParaGerenciar = null;
    },

    async confirmarGerenciar() {
        const item = this.itemParaGerenciar;
        if (!item) return;

        const orgao = item.orgaoEntidade || {};
        const unidade = item.unidadeOrgao || {};
        const criarLembrete = document.getElementById('gerenciarCriarLembrete')?.checked ?? true;
        const antecedencia = parseInt(document.getElementById('gerenciarAntecedencia')?.value || '24', 10);
        const statusInicial = document.getElementById('gerenciarStatus')?.value || 'em_analise';
        const observacoes = document.getElementById('gerenciarObs')?.value.trim() || null;

        const payload = {
            numero_controle_pncp: item.numeroControlePNCP || '',
            orgao_razao_social: orgao.razaoSocial || 'Não informado',
            objeto_compra: item.objetoCompra || 'Sem descrição',
            modalidade_nome: item.modalidadeNome || null,
            uf: unidade.ufSigla || null,
            municipio: unidade.municipioNome || null,
            valor_estimado: item.valorTotalEstimado || null,
            data_abertura: item.dataAberturaProposta || null,
            link_sistema_origem: item.linkSistemaOrigem || null,
            dados_completos: item,
            status_inicial: statusInicial,
            observacoes: observacoes,
            criar_lembrete: criarLembrete,
            antecedencia_horas: antecedencia,
        };

        const btnConfirmar = document.querySelector('[data-action="confirmarGerenciar"]');
        if (btnConfirmar) {
            btnConfirmar.disabled = true;
            btnConfirmar.textContent = 'Salvando...';
        }

        try {
            const response = await api.post('/pncp/gerenciar', payload);

            if (response.licitacao_ja_existia) {
                ui.showToast('Esta licitação já está no seu gerenciamento.', 'warning');
            } else {
                const lembreteMsg = response.lembrete_id
                    ? ` Lembrete criado no Calendário.`
                    : '';
                ui.showToast(`Licitação adicionada!${lembreteMsg}`, 'success');

                // Marcar o card como gerenciado
                this._marcarCardGerenciado(item.numeroControlePNCP);
            }
            this.fecharModalGerenciar();
        } catch (err) {
            const msg = err?.detail || 'Erro ao gerenciar licitação. Tente novamente.';
            ui.showToast(Sanitize.escapeHtml(msg), 'error');
        } finally {
            if (btnConfirmar) {
                btnConfirmar.disabled = false;
                btnConfirmar.textContent = '→ Gerenciar';
            }
        }
    },

    _marcarCardGerenciado(numeroControle) {
        // Encontrar o botão do card e marcá-lo como gerenciado
        const cards = document.querySelectorAll('.licitacao-card');
        cards.forEach(card => {
            const btn = card.querySelector('.card-btn-gerenciar');
            if (btn) {
                const idx = parseInt(btn.dataset.index, 10);
                const item = this.resultados[idx];
                if (item && item.numeroControlePNCP === numeroControle) {
                    btn.textContent = '✓ Gerenciado';
                    btn.classList.add('gerenciado');
                    btn.disabled = true;
                    btn.removeAttribute('data-action');
                }
            }
        });
    },
};

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    if (typeof api !== 'undefined' && typeof ui !== 'undefined') {
        EncontrarModule.init();
    } else {
        console.error('Encontrar: dependências (api, ui) não carregadas');
    }
});
