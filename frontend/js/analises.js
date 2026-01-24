/* JavaScript especifico da pagina de analises */

let arquivoSelecionado = null;

document.addEventListener('DOMContentLoaded', () => {
    carregarAnalises();
    setupUploadAnalise();
    setupFormNovaAnalise();

    // Verificar se ha ID na URL
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (id) {
        carregarDetalheAnalise(id);
    }
});

async function carregarAnalises() {
    try {
        const response = await api.get('/analises/');
        const analises = response.items || [];
        const container = document.getElementById('listaAnalises');

        if (analises.length === 0) {
            container.innerHTML = `
                <div class="card empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <h3>Nenhuma analise realizada</h3>
                    <p class="text-muted">Faca sua primeira analise de licitacao</p>
                </div>
            `;
            return;
        }

        container.innerHTML = analises.map(a => {
            const status = a.resultado_json ?
                (a.resultado_json.every(r => r.status === 'atende') ? 'atende' :
                 a.resultado_json.some(r => r.status === 'atende') ? 'parcial' : 'nao-atende') :
                'pendente';

            const statusIcon = {
                'atende': '✅',
                'parcial': '⚠️',
                'nao-atende': '❌',
                'pendente': '⏳'
            }[status];

            const statusText = {
                'atende': 'Atende todos os requisitos',
                'parcial': 'Atende parcialmente',
                'nao-atende': 'Nao atende',
                'pendente': 'Aguardando processamento'
            }[status];

            return `
                <div class="card">
                    <div class="d-flex justify-between align-center">
                        <div>
                            <h3>${a.nome_licitacao}</h3>
                            <p class="text-muted">${formatarData(a.created_at)}</p>
                            <span class="badge badge-${status === 'atende' ? 'success' : status === 'parcial' ? 'warning' : 'error'}">
                                ${statusIcon} ${statusText}
                            </span>
                        </div>
                        <div class="d-flex gap-1">
                            <button class="btn btn-primary btn-sm" onclick="carregarDetalheAnalise(${a.id})">Ver Detalhes</button>
                            ${!a.resultado_json ? `<button class="btn btn-outline btn-sm" onclick="processarAnalise(${a.id})">Processar</button>` : ''}
                            <button class="btn btn-danger btn-sm" onclick="excluirAnalise(${a.id})">Excluir</button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        ui.showAlert('Erro ao carregar analises', 'error');
    }
}

async function carregarDetalheAnalise(id) {
    try {
        const analise = await api.get(`/analises/${id}`);
        document.getElementById('listaAnalises').classList.add('hidden');
        document.getElementById('detalheAnalise').classList.remove('hidden');
        document.getElementById('analiseNome').textContent = analise.nome_licitacao;

        const container = document.getElementById('resultadoAnalise');

        if (!analise.resultado_json || analise.resultado_json.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>Esta analise ainda nao foi processada.</p>
                    <button class="btn btn-primary mt-2" onclick="processarAnalise(${id})">Processar Agora</button>
                </div>
            `;
            return;
        }

        container.innerHTML = analise.resultado_json.map(r => {
            const statusIcon = r.status === 'atende' ? '✅' : r.status === 'parcial' ? '⚠️' : '❌';
            const statusClass = r.status === 'atende' ? 'success' : r.status === 'parcial' ? 'warning' : 'error';
            const exigenciaDescricao = r.exigencia?.descricao || 'Exigencia sem descricao';
            const exigenciaQuantidade = r.exigencia?.quantidade_minima;
            const exigenciaUnidade = r.exigencia?.unidade || '-';

            return `
                <div class="card resultado-card">
                    <div class="resultado-header">
                        <div>
                            <h3>${exigenciaDescricao}</h3>
                            <p class="text-muted">
                                Minimo exigido: ${formatarNumero(exigenciaQuantidade)} ${exigenciaUnidade}
                            </p>
                        </div>
                        <div class="resultado-status status-${statusClass}">
                            <span class="status-icon">${statusIcon}</span>
                            <span>${r.percentual_total.toFixed(1)}%</span>
                        </div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill ${r.status}" style="width: ${Math.min(r.percentual_total, 100)}%"></div>
                    </div>
                    ${r.atestados_recomendados.length > 0 ? `
                        <div class="atestado-lista mt-2">
                            <strong>Atestados recomendados:</strong>
                            ${r.atestados_recomendados.map(at => `
                                <div class="atestado-item">
                                    <span>${at.descricao_servico}</span>
                                    <span>${formatarNumero(at.quantidade)} ${at.unidade || '-'} (${at.percentual_cobertura.toFixed(1)}%)</span>
                                </div>
                                ${(at.itens && at.itens.length) ? `
                                    <details class="atestado-itens">
                                        <summary>Itens usados (${at.itens.length})</summary>
                                        ${at.itens.map(item => `
                                            <div class="atestado-item-detail">
                                                <span>${item.item ? item.item + ' - ' : ''}${item.descricao || '-'}</span>
                                                <span>${formatarNumero(item.quantidade)} ${item.unidade || '-'}</span>
                                            </div>
                                        `).join('')}
                                    </details>
                                ` : ''}
                            `).join('')}
                            <div class="atestado-item" style="font-weight: bold;">
                                <span>Total</span>
                                <span>${formatarNumero(r.soma_quantidades)} ${exigenciaUnidade}</span>
                            </div>
                        </div>
                    ` : '<p class="text-muted mt-2">Nenhum atestado compativel encontrado.</p>'}
                </div>
            `;
        }).join('');

    } catch (error) {
        ui.showAlert('Erro ao carregar analise', 'error');
    }
}

function voltarLista() {
    document.getElementById('listaAnalises').classList.remove('hidden');
    document.getElementById('detalheAnalise').classList.add('hidden');
    window.history.pushState({}, '', 'analises.html');
}

function setupUploadAnalise() {
    const zone = document.getElementById('uploadZoneAnalise');
    const input = document.getElementById('fileInputAnalise');

    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file && file.type === 'application/pdf') {
            arquivoSelecionado = file;
            document.getElementById('nomeArquivo').textContent = `Arquivo: ${file.name}`;
        }
    });

    input.addEventListener('change', () => {
        if (input.files[0]) {
            arquivoSelecionado = input.files[0];
            document.getElementById('nomeArquivo').textContent = `Arquivo: ${arquivoSelecionado.name}`;
        }
    });
}

function setupFormNovaAnalise() {
    document.getElementById('formNovaAnalise').addEventListener('submit', async (e) => {
        e.preventDefault();

        const nomeLicitacao = document.getElementById('nomeLicitacao').value;
        if (!arquivoSelecionado) {
            ui.showAlert('Selecione o PDF do edital', 'error');
            return;
        }

        const button = e.target.querySelector('button[type="submit"]');
        ui.setButtonLoading(button, true, 'btnAnaliseText', 'btnAnaliseSpinner');

        try {
            const formData = new FormData();
            formData.append('nome_licitacao', nomeLicitacao);
            formData.append('file', arquivoSelecionado);

            const result = await api.upload('/analises/?nome_licitacao=' + encodeURIComponent(nomeLicitacao), formData);

            ui.showAlert('Analise criada com sucesso!', 'success');
            fecharModal('modalNovaAnalise');
            arquivoSelecionado = null;
            document.getElementById('formNovaAnalise').reset();
            document.getElementById('nomeArquivo').textContent = '';
            carregarAnalises();

            // Processar automaticamente
            if (result.id) {
                processarAnalise(result.id);
            }

        } catch (error) {
            ui.showAlert(error.message || 'Erro ao criar analise', 'error');
        } finally {
            ui.setButtonLoading(button, false, 'btnAnaliseText', 'btnAnaliseSpinner');
        }
    });
}

function abrirModalNovaAnalise() {
    arquivoSelecionado = null;
    document.getElementById('formNovaAnalise').reset();
    document.getElementById('nomeArquivo').textContent = '';
    document.getElementById('modalNovaAnalise').classList.add('active');
}

async function processarAnalise(id) {
    try {
        ui.showAlert('Processando analise...', 'info');
        await api.post(`/analises/${id}/processar`);
        ui.showAlert('Analise processada com sucesso!', 'success');
        carregarAnalises();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao processar analise', 'error');
    }
}

async function excluirAnalise(id) {
    if (!confirm('Tem certeza que deseja excluir esta analise?')) return;

    try {
        await api.delete(`/analises/${id}`);
        ui.showAlert('Analise excluida com sucesso!', 'success');
        carregarAnalises();
    } catch (error) {
        ui.showAlert(error.message || 'Erro ao excluir analise', 'error');
    }
}
