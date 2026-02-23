/**
 * Modulo de Calendario de Lembretes.
 */
const CalendarioModule = {
    mesAtual: new Date().getMonth(),
    anoAtual: new Date().getFullYear(),
    lembretes: [],
    diaSelecionado: null,

    async init() {
        this.renderCalendario();
        this.setupEvents();
        // Aguardar auth config antes de fazer chamadas API
        await loadAuthConfig();
        this.carregarLembretes();
    },

    setupEvents() {
        document.addEventListener('click', (e) => {
            const action = e.target.closest('[data-action]');
            if (!action) return;

            const actionName = action.dataset.action;
            switch (actionName) {
                case 'mes-anterior':
                    e.preventDefault();
                    this.navegarMes(-1);
                    break;
                case 'mes-proximo':
                    e.preventDefault();
                    this.navegarMes(1);
                    break;
                case 'selecionar-dia':
                    e.preventDefault();
                    this.selecionarDia(parseInt(action.dataset.dia), parseInt(action.dataset.mes), parseInt(action.dataset.ano));
                    break;
                case 'novo-lembrete':
                    e.preventDefault();
                    this.abrirModal();
                    break;
                case 'excluir-lembrete': {
                    e.preventDefault();
                    const id = action.dataset.id;
                    if (id) this.excluirLembrete(id);
                    break;
                }
                case 'cancelar-lembrete': {
                    e.preventDefault();
                    const cid = action.dataset.id;
                    if (cid) this.mudarStatus(cid, 'cancelado');
                    break;
                }
            }
        });

        // Form submit
        const form = document.getElementById('formLembrete');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.salvarLembrete();
            });
        }
    },

    renderCalendario() {
        const grid = document.getElementById('calendarioGrid');
        const titulo = document.getElementById('calendarioTitulo');
        if (!grid || !titulo) return;

        const meses = [
            'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
        ];
        titulo.textContent = `${meses[this.mesAtual]} ${this.anoAtual}`;

        const hoje = new Date();
        const primeiroDia = new Date(this.anoAtual, this.mesAtual, 1);
        const ultimoDia = new Date(this.anoAtual, this.mesAtual + 1, 0);
        const inicioSemana = primeiroDia.getDay(); // 0=Dom
        const totalDias = ultimoDia.getDate();

        // Dias do mes anterior para preencher
        const mesAnteriorUltimo = new Date(this.anoAtual, this.mesAtual, 0).getDate();

        let html = '';

        // Dias do mes anterior
        for (let i = inicioSemana - 1; i >= 0; i--) {
            const dia = mesAnteriorUltimo - i;
            const mesAnt = this.mesAtual - 1;
            const anoAnt = mesAnt < 0 ? this.anoAtual - 1 : this.anoAtual;
            const mesReal = mesAnt < 0 ? 11 : mesAnt;
            html += `<div class="calendario-dia outro-mes" data-action="selecionar-dia" data-dia="${dia}" data-mes="${mesReal}" data-ano="${anoAnt}">
                <div class="dia-numero">${dia}</div>
                <div class="dia-indicadores" id="ind-${anoAnt}-${mesReal}-${dia}"></div>
            </div>`;
        }

        // Dias do mes atual
        for (let dia = 1; dia <= totalDias; dia++) {
            const isHoje = dia === hoje.getDate() && this.mesAtual === hoje.getMonth() && this.anoAtual === hoje.getFullYear();
            const isSelecionado = this.diaSelecionado && dia === this.diaSelecionado.dia && this.mesAtual === this.diaSelecionado.mes && this.anoAtual === this.diaSelecionado.ano;
            const classes = ['calendario-dia'];
            if (isHoje) classes.push('hoje');
            if (isSelecionado) classes.push('selecionado');

            html += `<div class="${classes.join(' ')}" data-action="selecionar-dia" data-dia="${dia}" data-mes="${this.mesAtual}" data-ano="${this.anoAtual}">
                <div class="dia-numero">${dia}</div>
                <div class="dia-indicadores" id="ind-${this.anoAtual}-${this.mesAtual}-${dia}"></div>
            </div>`;
        }

        // Dias do proximo mes para completar grid
        const celulasUsadas = inicioSemana + totalDias;
        const restante = celulasUsadas % 7 === 0 ? 0 : 7 - (celulasUsadas % 7);
        for (let dia = 1; dia <= restante; dia++) {
            const mesProx = this.mesAtual + 1;
            const anoProx = mesProx > 11 ? this.anoAtual + 1 : this.anoAtual;
            const mesReal = mesProx > 11 ? 0 : mesProx;
            html += `<div class="calendario-dia outro-mes" data-action="selecionar-dia" data-dia="${dia}" data-mes="${mesReal}" data-ano="${anoProx}">
                <div class="dia-numero">${dia}</div>
                <div class="dia-indicadores" id="ind-${anoProx}-${mesReal}-${dia}"></div>
            </div>`;
        }

        grid.innerHTML = html;
    },

    async carregarLembretes() {
        const inicio = new Date(this.anoAtual, this.mesAtual, 1);
        const fim = new Date(this.anoAtual, this.mesAtual + 1, 0, 23, 59, 59);

        try {
            const resp = await api.get(
                `/lembretes/calendario?data_inicio=${inicio.toISOString()}&data_fim=${fim.toISOString()}`
            );
            this.lembretes = resp || [];
            this.marcarIndicadores();

            // Se tem dia selecionado, atualizar painel
            if (this.diaSelecionado) {
                this.renderListaDia();
            }
        } catch {
            this.lembretes = [];
        }
    },

    marcarIndicadores() {
        // Limpar todos
        document.querySelectorAll('.dia-indicadores').forEach(el => el.innerHTML = '');

        for (const lem of this.lembretes) {
            const d = new Date(lem.data_lembrete);
            const container = document.getElementById(`ind-${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`);
            if (container) {
                const statusClass = lem.status === 'enviado' ? ' enviado' : lem.status === 'cancelado' ? ' cancelado' : '';
                container.innerHTML += `<span class="dia-indicador${statusClass}"></span>`;
            }
        }
    },

    navegarMes(delta) {
        this.mesAtual += delta;
        if (this.mesAtual > 11) {
            this.mesAtual = 0;
            this.anoAtual++;
        } else if (this.mesAtual < 0) {
            this.mesAtual = 11;
            this.anoAtual--;
        }
        this.diaSelecionado = null;
        this.renderCalendario();
        this.carregarLembretes();
        this.renderListaDia();
    },

    selecionarDia(dia, mes, ano) {
        this.diaSelecionado = { dia, mes, ano };

        // Se clicou em dia de outro mes, navegar
        if (mes !== this.mesAtual || ano !== this.anoAtual) {
            this.mesAtual = mes;
            this.anoAtual = ano;
            this.renderCalendario();
            this.carregarLembretes();
        } else {
            // Atualizar selecao visual
            document.querySelectorAll('.calendario-dia').forEach(el => el.classList.remove('selecionado'));
            const diaEl = document.querySelector(
                `.calendario-dia[data-dia="${dia}"][data-mes="${mes}"][data-ano="${ano}"]:not(.outro-mes)`
            );
            if (diaEl) diaEl.classList.add('selecionado');
        }

        this.renderListaDia();
    },

    renderListaDia() {
        const painel = document.getElementById('lembretesDia');
        const tituloEl = document.getElementById('diaSelecionadoTitulo');
        if (!painel) return;

        if (!this.diaSelecionado) {
            if (tituloEl) tituloEl.textContent = 'Selecione um dia';
            painel.innerHTML = '<div class="lembretes-vazio">Clique em um dia para ver lembretes</div>';
            return;
        }

        const { dia, mes, ano } = this.diaSelecionado;
        if (tituloEl) tituloEl.textContent = `${String(dia).padStart(2, '0')}/${String(mes + 1).padStart(2, '0')}/${ano}`;

        const lembretesDoDia = this.lembretes.filter(lem => {
            const d = new Date(lem.data_lembrete);
            return d.getDate() === dia && d.getMonth() === mes && d.getFullYear() === ano;
        });

        if (lembretesDoDia.length === 0) {
            painel.innerHTML = '<div class="lembretes-vazio">Nenhum lembrete neste dia</div>';
            return;
        }

        painel.innerHTML = lembretesDoDia.map(lem => {
            const hora = new Date(lem.data_lembrete).toLocaleTimeString('pt-BR', {
                hour: '2-digit', minute: '2-digit'
            });
            const titulo = Sanitize.escapeHtml(lem.titulo);
            const desc = lem.descricao ? Sanitize.escapeHtml(lem.descricao) : '';
            const statusClass = lem.status === 'enviado' ? ' enviado' : lem.status === 'cancelado' ? ' cancelado' : '';

            return `
                <div class="lembrete-card${statusClass}">
                    <div class="lembrete-titulo">${titulo}</div>
                    <div class="lembrete-hora">${hora} - ${Sanitize.escapeHtml(lem.status)}</div>
                    ${desc ? `<div class="lembrete-desc">${desc}</div>` : ''}
                    <div class="lembrete-acoes">
                        ${lem.status === 'pendente' ? `<button class="btn btn-sm btn-outline" data-action="cancelar-lembrete" data-id="${lem.id}">Cancelar</button>` : ''}
                        <button class="btn btn-sm btn-outline" data-action="excluir-lembrete" data-id="${lem.id}">Excluir</button>
                    </div>
                </div>
            `;
        }).join('');
    },

    abrirModal() {
        const modal = document.getElementById('modalLembrete');
        if (!modal) return;
        modal.classList.add('active');

        // Pre-preencher data se tem dia selecionado
        const inputData = document.getElementById('lembreteData');
        if (inputData && this.diaSelecionado) {
            const { ano, mes, dia } = this.diaSelecionado;
            inputData.value = `${ano}-${String(mes + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}T09:00`;
        }

        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) firstInput.focus();
    },

    async salvarLembrete() {
        const titulo = document.getElementById('lembreteTitulo')?.value?.trim();
        const descricao = document.getElementById('lembreteDescricao')?.value?.trim();
        const dataLembrete = document.getElementById('lembreteData')?.value;
        const tipo = document.getElementById('lembreteTipo')?.value || 'manual';

        if (!titulo || !dataLembrete) {
            ui.showAlert('Título e data são obrigatórios', 'error');
            return;
        }

        try {
            await api.post('/lembretes/', {
                titulo,
                descricao: descricao || null,
                data_lembrete: new Date(dataLembrete).toISOString(),
                tipo,
                canais: ['app'],
            });

            ui.showAlert('Lembrete criado com sucesso!', 'success');

            // Fechar modal e recarregar
            const modal = document.getElementById('modalLembrete');
            if (modal) modal.classList.remove('active');
            document.getElementById('formLembrete')?.reset();

            this.carregarLembretes();
        } catch (err) {
            ui.showAlert('Erro ao criar lembrete', 'error');
        }
    },

    async excluirLembrete(id) {
        if (typeof confirmAction === 'function') {
            const ok = await confirmAction('Tem certeza que deseja excluir este lembrete?');
            if (!ok) return;
        }

        try {
            await api.delete(`/lembretes/${id}`);
            ui.showAlert('Lembrete excluído', 'success');
            this.carregarLembretes();
        } catch {
            ui.showAlert('Erro ao excluir lembrete', 'error');
        }
    },

    async mudarStatus(id, status) {
        try {
            await api.patch(`/lembretes/${id}/status`, { status });
            this.carregarLembretes();
        } catch {
            ui.showAlert('Erro ao mudar status', 'error');
        }
    },
};

// Init
document.addEventListener('DOMContentLoaded', () => {
    CalendarioModule.init();
});
