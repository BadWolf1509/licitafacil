# Plano de implementacao por sprints

Objetivo: decidir se o licitante atende a quantidade exigida por servico e apontar quais atestados devem ser apresentados, considerando soma entre atestados quando permitido.

## Premissas
- Matching deve operar por item de servico (servicos_json), nao apenas por descricao_servico do atestado.
- Soma de atestados e permitida por padrao; restricoes do edital devem sobrescrever essa regra.
- LLM e opcional e deve explicar resultados, nao substituir a logica deterministica.

## Sprint 1 - Motor de matching e contratos

Escopo:
- Criar servico deterministico de matching (ex: backend/services/matching_service.py).
- Normalizar unidades e descricoes antes de comparar.
- Definir contratos de entrada/saida com dados de contribuicao por atestado.

Tarefas:
- Implementar matching por unidade + similaridade de descricao (keywords) + thresholds.
- Somar quantidades por exigencia e calcular percentual atendido.
- Selecionar atestados recomendados (greedy por maior contribuicao).
- Atualizar schemas em backend/schemas.py (ResultadoExigencia, AtestadoMatch, ExigenciaEdital) para refletir o output real.
- Atualizar document_processor.analyze_qualification para chamar o novo servico.
- Tests unitarios para matching (unidade, similaridade, soma, selecao).

Aceite:
- Dado um conjunto de servicos_json e exigencias, retorna status atende/parcial/nao_atende, percentual e lista de atestados recomendados com contribuicao.

Riscos:
- Similaridade de descricao gerar falso positivo. Mitigacao: limiar configuravel e log de score.

## Sprint 2 - Integracao com analises

Escopo:
- Conectar analise de edital ao matching por item.
- Capturar restricoes do edital sobre soma.

Tarefas:
- Em routers/analise.py, montar input do matching usando servicos_json de cada atestado.
- Estender extract_edital_requirements para capturar restricao de soma (ex: permitir_soma, exige_unico).
- Ajustar persistencia de resultado_json no modelo Analise.
- Remover ou deixar obsoleto o prompt analise_matching.txt (ou usar apenas para explicacao).

Aceite:
- Analise de edital usa servicos_json e gera recomendacao de atestados por exigencia.
- Restricao de soma e respeitada quando presente.

Riscos:
- Edital nao explicitar restricao; default pode ser incorreto. Mitigacao: default documentado + campo de override manual.

## Sprint 3 - UI de analises

Escopo:
- Exibir resultados do matching com clareza operacional.

Tarefas:
- Atualizar frontend/analises.html e JS para mostrar:
  - exigencia, quantidade exigida e atendida
  - status e percentual
  - atestados recomendados e contribuicao por atestado
  - itens do atestado que suportam a exigencia
- Ajustar formatos numericos e unidades no front.

Aceite:
- Usuario consegue ver claramente quais atestados apresentar e qual soma atende cada exigencia.

Riscos:
- Dados volumosos por exigencia. Mitigacao: collapse por exigencia e lazy render de itens.

## Sprint 4 - Qualidade e confiabilidade

Escopo:
- Validacao sistematica e observabilidade do matching.

Tarefas:
- Criar fixtures de testes com exigencias e atestados reais anonimizados.
- Teste de regressao: soma correta, unidade compatvel, restricao de soma.
- Logs estruturados para auditoria de decisao (score, unidade, itens usados).
- Documentar limites conhecidos e configuracoes criticas no README.

Aceite:
- Suite de testes cobrindo casos chave e logs suficientes para auditoria.

Riscos:
- Dados reais incompletos. Mitigacao: usar conjunto minimo validado e expandir iterativamente.
