# Plano de implementação — Classificação de postura e queda

Data: 2026-09-10. Base verificada: branch `ajustes/integracao-backend-v2`, com alterações locais da integração v2.

Status atualizado: desenho e aplicação aprovados pelo usuário; migração validada em PostgreSQL temporário e aplicada ao banco configurado com backup verificado e `psql --single-transaction --set=ON_ERROR_STOP=1`. API e worker reiniciados. A suíte final tem 52 testes aprovados, incluindo a correção necessária para o subprocesso Windows. Redis e conexão física das câmeras continuam pendentes. Este documento preserva a sequência planejada; o estado efetivo e as evidências estão em `RELATORIO_AJUSTES_BACKEND_V2.md`, e o contrato vigente está em `CONTRATO_INTEGRACAO.md`.

Referências: `CONTRATO_INTEGRACAO.md`, `RELATORIO_AJUSTES_BACKEND_V2.md` e código atual desta branch. Preservar as alterações locais existentes ao executar o plano.

## 1. Resultado esperado

O frontend poderá consultar e receber em tempo real eventos de tronco, rotação e queda, distinguindo-os dos alertas de EPI por um campo estruturado. Novos eventos de postura pertencerão à câmera, sem inventar vínculo com zona, monitoramento ou equipamento.

Permanecem as regras atuais de severidade, responsáveis, emissão única por chamada e cooldown. A queda continua com severidade 3; tronco e rotação mantêm a severidade atual. Não haverá inferência do tipo por palavras do campo `evento`.

## 2. Diagnóstico confirmado no código

| Ponto | Estado atual | Consequência para a implementação |
| --- | --- | --- |
| `services/visao_service.py` | `_registrar_alerta_postura` retorna sem salvar se não há zonas e seleciona `zonas[0]` quando existem. | Remover a dependência de zona para registrar postura, inclusive em câmera sem zonas. |
| `assets/tabelas_spi-postgres.sql` | `alertas.id_monitorar` é obrigatório e não existe `alertas.id_camera`. | Só acrescentar `tipo_deteccao` não resolve o vínculo arbitrário. |
| `repository/alertas_repository.py` | Listagens e detalhe usam `JOIN` obrigatório com monitoramento e zona. | Esses joins precisam aceitar alertas vinculados diretamente à câmera. |
| `services/alertas_service.py` | Resolução acessa `monitoramento['id_monitorar']` sem verificar ausência. | Resolver postura ou um ID inexistente pode causar erro se esse fluxo não for adaptado. |
| Payload `novo_alerta` | Ambos os caminhos já incluem `id_usuario`, localização e nomes. | Acrescentar o tipo, preservar todas as chaves e definir os nulos de postura. |
| Estatísticas de EPI | Contam alertas pelo vínculo com equipamento, sem tipo explícito. | Separar novos eventos classificados e explicitar o tratamento do histórico. |
| Infraestrutura de testes | Existem testes `unittest`, cliente Flask/Socket.IO e PostgreSQL com tabelas temporárias. | Estender o padrão existente; o resultado de 26 testes documentado é da etapa anterior. |

O diagnóstico de schema acima se baseia no DDL versionado. A implementação deverá conferir o catálogo do banco em modo somente leitura antes de preparar a migração definitiva; nenhuma conexão ao banco foi realizada para elaborar este plano.

## 3. Modelo de dados proposto para aprovação

Usar a tabela `alertas`, com duas novas colunas e alteração de nulabilidade:

| Campo | Proposta |
| --- | --- |
| `tipo_deteccao` | `VARCHAR(20) NOT NULL`, com `CHECK`, default `epi` para novas inserções. Tipos operacionais: `epi`, `postura_tronco`, `postura_rotacao`, `queda`. |
| `id_camera` | Inteiro opcional, FK para `cameras(id_camera)` com `ON DELETE RESTRICT`, obrigatório para postura/queda. |
| `id_monitorar` | Permitir `NULL`; continuar obrigatório para EPI. Preservar a FK existente. |

Recomendação adicional: permitir `legado` exclusivamente para registros anteriores à migração. Esse marcador significa origem desconhecida, não uma quinta detecção do modelo. O serviço deverá rejeitá-lo na criação de novos alertas.

Aplicar default `epi` a todo o histórico daria aparência de precisão a dados que já misturam EPI e postura. Preservar os registros antigos como `legado`, incluindo seus vínculos originais, sem tentar reclassificá-los pelo texto. Uma recuperação histórica baseada em evidência poderá ser decidida separadamente.

Invariantes da proposta:

- EPI: `id_monitorar IS NOT NULL` e `alertas.id_camera IS NULL`. A câmera continua sendo derivada da zona nas respostas, sem duplicar a relação já existente.
- Postura/queda: `id_monitorar IS NULL` e `alertas.id_camera IS NOT NULL`. Nas respostas, `id_zona`, `id_epi` e `nome_zona` serão `null`.
- Legado: conservar `id_monitorar` e deixar a nova coluna de câmera nula. A localização continuará derivada do vínculo histórico, sem atestar sua precisão para postura.
- FK e `CHECK` devem impedir câmera inexistente, tipo desconhecido, postura com monitoramento e EPI sem monitoramento.

Preferir texto com `CHECK` a enum nativo PostgreSQL para manter a alteração simples e explícita em SQL. Não introduzir ORM nem framework de migrações nesta entrega.

### Sequência da migração, após confirmação

1. Conferir colunas, constraints, quantidade de alertas e relações existentes; preparar backup e janela curta sem gravação de alertas.
2. Criar um script incremental versionado em `assets/migrations/`, separado do DDL de instalação. O arquivo `tabelas_spi-postgres.sql` começa com `DROP TABLE`; não executá-lo sobre o banco existente.
3. Em transação, adicionar `tipo_deteccao` com default inicial `legado`, preenchendo o histórico, e depois mudar somente o default para `epi`.
4. Adicionar `id_camera` e sua FK; permitir `id_monitorar` nulo; adicionar as constraints de domínio e vínculo descritas acima.
5. Validar conservação de IDs, quantidade, usuários, eventos, severidades e relações dos registros anteriores; confirmar a transação somente com as validações aprovadas.
6. Atualizar o DDL de instalação para refletir o estado final, sem executá-lo como migração.
7. Disponibilizar o backend atualizado e reiniciar API/workers antes de retomar a captura. Workers antigos não podem continuar inserindo postura com o default `epi`.

Antes de novas gravações, uma falha de DDL deve provocar rollback transacional. Após existir postura sem monitoramento, remover colunas ou restaurar a obrigatoriedade de `id_monitorar` deixa de ser reversão segura: interromper gravações e corrigir a versão, ou restaurar backup com decisão explícita sobre os dados posteriores. Não excluir alertas para viabilizar downgrade.

## 4. Persistência, serviços e visão

Implementar nesta ordem:

1. Centralizar tipos válidos e o grupo `postura` em um pequeno módulo de domínio. Separar tipos aceitos para criação dos valores aceitos em consulta, que também incluem `legado`.
2. Atualizar `models/alertas.py`: acrescentar `tipo_deteccao` e aceitar nulos em `id_monitorar` e `id_zona`.
3. Atualizar `AlertasRepository.criar_alerta` para persistir tipo e câmera direta. Usar parâmetros SQL, validar combinações antes do INSERT e garantir rollback em erro de persistência.
4. Adequar todas as leituras de alertas: geral, câmera, zona, usuário e detalhe. Usar `LEFT JOIN` para monitoramento/zona e `COALESCE(a.id_camera, z.id_camera)` como câmera efetiva. A listagem por zona naturalmente não inclui postura sem zona. Centralizar o mapeamento da linha para evitar divergências entre consultas.
5. Acrescentar o tipo a todas as respostas REST de alertas. Preservar IDs, datas, formato do array e demais campos existentes.
6. Ajustar `criar_alerta` para aceitar contexto de câmera sem fabricar objeto de zona. O caminho EPI de `registrar_alertas_com_notificacao_unica` mantém monitoramento obrigatório e default `epi`; o caminho de postura exige tipo explícito.
7. Em `_batch_pose_estimation`, passar `postura_tronco`, `postura_rotacao` ou `queda` diretamente do ramo correspondente para `_registrar_alerta_postura`. Preservar geometria, limiares, textos de evento, severidades e requisito atual de tracking válido.
8. Em `_registrar_alerta_postura`, eliminar a consulta de zonas como requisito de persistência. Validar a câmera e obter setor/responsáveis por ela. Câmera inexistente não gera INSERT, Socket.IO ou e-mail; falhas devem ser tratadas e registradas sem derrubar o processamento das demais câmeras.
9. Ajustar resolução: retornar falha de forma controlada quando o alerta não existe; após sucesso, consultar/enviar `RESET` apenas quando existir monitoramento e alarme associado. Resolver postura somente altera o estado do alerta.

Preservar a quantidade de registros e notificações: EPI continua com registro por responsável e uma emissão que referencia o primeiro usuário efetivamente salvo; postura continua com registro único, primeiro responsável como `id_usuario` ou `null`, e todos os destinatários atuais para e-mail crítico. Nenhuma emissão ocorre quando a persistência falha.

As chaves permanecem exatamente `lock:alerta:epi:{id_monitorar}:{evento}:{track_id}` e `lock:alerta:postura:{camera_id}:{track_id}:{motivo}`, com `SET NX EX 30`. Não alterar motivo para incorporar tipo, nem adicionar outra trava que mude o comportamento. Manter `ALERT_DIAGNOSTICS`.

## 5. Consulta HTTP proposta

Reutilizar `GET /alertas` com parâmetro opcional `tipo`, também nas listagens existentes por câmera e zona.

| Exemplo | Seleção |
| --- | --- |
| `/alertas` | Todos os tipos, incluindo legado. |
| `/alertas?tipo=epi` | Somente EPI identificado explicitamente. |
| `/alertas?tipo=postura` | Grupo `postura_tronco`, `postura_rotacao` e `queda`. |
| `/alertas?tipo=queda` | Somente queda. |
| `/alertas?tipo=postura_tronco` ou `tipo=postura_rotacao` | Subtipo exato. |
| `/alertas?tipo=legado` | Histórico de origem não identificada. |
| `/alertas/camera/1?tipo=postura` | Classificação da câmera solicitada. |

Validar uma única ocorrência de `tipo`, com valor exato da lista permitida. Vazio, texto desconhecido, espaços adicionais, maiúsculas não previstas e parâmetros `tipo` repetidos retornam **400** com `{"message":"tipo inválido; informe um dos valores permitidos."}`. Aplicar filtro no SQL, sem interpolar valores nem filtrar só após carregar todos os registros.

Preservar o contrato atual das listagens: **200** com array não vazio e **404** com objeto `message` quando não há resultados. Nas rotas por câmera/zona, ID inexistente e recurso sem alertas continuam produzindo 404 de ausência de resultados. Não introduzir uma distinção nova de existência nesta entrega. A rota de detalhe conserva 200/404; resolver alerta inexistente conserva a resposta de falha 400 atual, sem exceção por acesso a `None`.

Nas estatísticas, `/alertas/estatisticas/epi` passará a contar apenas `tipo_deteccao='epi'`, preservando `Sem Categoria` para EPI sem categoria. O histórico `legado` ficará fora desse gráfico; documentar a possível redução de totais. `/alertas/estatisticas/periodo` manterá todos os registros e o contrato atual de `periodo`. Filtros e gráficos adicionais de classificação ficam para outra etapa.

## 6. WebSocket e exemplo de consumo

Acrescentar `tipo_deteccao` à montagem compartilhada de `novo_alerta`, preservando as chaves existentes. Para postura, obter `nome_setor` pelo setor da câmera; a consulta atual por zona não atende esse caso.

Exemplo proposto para queda:

```json
{
  "id_monitorar": null,
  "id_usuario": 4,
  "id_camera": 1,
  "id_zona": null,
  "nome_zona": null,
  "nome_camera": "Câmera 1",
  "nome_setor": "Produção",
  "evento": "Queda detectada",
  "severidade": 3,
  "tipo_deteccao": "queda"
}
```

O texto do evento acima é ilustrativo; a implementação preservará o motivo produzido pelo modelo. `id_usuario` será `null` sem responsável. Nomes continuam podendo ser nulos quando indisponíveis. Zona e monitoramento são nulos por não se aplicarem à classificação da câmera.

O WebSocket continua sem ID/data do alerta e sem identificação pessoal da pessoa detectada. A tela consulta REST para obter ID, data e estado de resolução. E-mails usam a câmera/setor e o fallback existente para zona ausente, preservando destinatários e fila RQ.

## 7. Testes e critérios de aceite

| Camada | Evidência necessária |
| --- | --- |
| Migração em PostgreSQL temporário | Executar o script incremental sobre estrutura anterior com dados de exemplo; conservar registros como legado; verificar default dos novos EPI, FK, CHECK e nulabilidade. Isolar em `pg_temp`, sem DDL nas tabelas reais. |
| Persistência real | Gravar e recuperar EPI, tronco, rotação e queda; consultar geral/câmera/zona/usuário/detalhe; provar que postura sem zona não desaparece nos joins. |
| Falhas de dados | Rejeitar câmera, monitoramento ou zona de origem inexistentes; tipo inválido; postura com monitoramento; EPI sem monitoramento. Após erro SQL, conexão utilizável e nenhuma notificação de gravação fracassada. |
| Visão simulada | Cada ramo fornece o tipo correto; câmera sem zonas gera postura; câmera inexistente não gera alerta; preservar severidade 3 para queda e bloqueio de tracking inválido. |
| Flask | Verificar grupo e subtipos, filtro por câmera/zona, parâmetros vazios/inválidos/repetidos, resultados vazios, IDs inexistentes e respostas 200/400/404. |
| Socket.IO local | Receber evento serializado com tipo, usuário e todas as chaves anteriores; verificar nulos de postura, nomes por câmera, emissão única e ausência de emissão em falha. |
| Responsáveis/RQ | EPI mantém registros por responsável; postura mantém registro único e todos os destinatários críticos. Sem responsáveis, usuário nulo e nenhum e-mail. Usar mock de envio, sem disparar mensagens reais. |
| Resolução/MQTT | Resolver postura sem procurar alarme arbitrário; resolver EPI mantém RESET quando aplicável; ID inexistente não causa 500. Simular comando, sem acionar equipamento. |
| Estatísticas/histórico | EPI exclui postura e legado; período mantém todos; legado consultável sem reclassificação pelo texto. |
| Regressão | Suíte existente de métricas, zonas, detecções e alertas; mesmas chaves, TTL e decisões de cooldown nos dois caminhos. |

Executar a suíte pelo comando já documentado no relatório, com `RUN_POSTGRES_TESTS=1` somente no ambiente de testes preparado. Fazer checagem sintática e `git diff --check`. Registrar quantidade efetiva de testes aprovados, falhas, skips e dependências simuladas; não reaproveitar a contagem antiga como evidência nova.

Redis entre processos, entrega real de e-mail, MQTT, navegador e inferência com câmera IP exigem validação integrada separada. A ausência desses recursos não permite afirmar funcionamento de ponta a ponta. O teste do `track_id` permanece pendente para a sessão com câmera física, conforme relatório anterior.

## 8. Documentação e entrega ao frontend

Após implementar e validar, atualizar `CONTRATO_INTEGRACAO.md` com campo novo, valores, filtros, HTTP, exemplos REST/Socket.IO e significado de cada nulo. Explicitar o marcador legado, a mudança das estatísticas de EPI e a manutenção de `periodo`.

Acrescentar uma seção de Classificação ao mesmo `RELATORIO_AJUSTES_BACKEND_V2.md`, explicando o problema, a decisão aprovada, o que foi efetivamente implementado, evidências e pendências. Não produzir outro relatório final nem descrever propostas como entregas concluídas.

Na rodada do frontend, sincronizar o contrato e:

- Consultar `tipo=postura` para Classificação e `tipo=epi` para Alertas de EPI.
- Tratar 404 de listagem como estado vazio; não confundir com erro 500.
- Rotear `novo_alerta` pelo tipo estruturado e buscar REST quando precisar de ID/data.
- Exibir câmera/setor e aceitar ausência de zona/EPI; oferecer acesso explícito ao histórico legado, sem apresentá-lo como classificação confirmada.
- Preservar atualização REST na indisponibilidade do Socket.IO.

O escopo de implementação deste plano é o backend. A tela do frontend, a decisão de cooldown, alterações nos modelos de visão, pooling PostgreSQL e coordenadas de câmera permanecem fora da entrega.

## 9. Ordem de execução e ponto de aprovação

1. Revisar e confirmar a proposta de schema, incluindo vínculo direto de postura à câmera e tratamento do histórico como legado.
2. Preparar migração incremental, alterações de código e testes isolados na branch atual, preservando o trabalho local.
3. Validar a implementação em PostgreSQL temporário e clientes de testes; apresentar o diff e resultados para revisão antes de aplicar ao banco configurado.
4. Aplicar a migração somente após a confirmação exigida pelo documento de origem, seguindo a janela de atualização de API/workers.
5. Atualizar contrato e relatório com o estado real da entrega e os limites da validação; disponibilizar as orientações de integração ao frontend.

Na etapa inicial de planejamento foi criado apenas este arquivo. Na execução subsequente, foram preparados código, migração e testes, e atualizados contrato/relatório. Após a revisão e autorização final, o banco foi migrado com backup e validação dos dados, e a API/worker foram reiniciados. O `.env` não foi editado; não houve commit ou push. A integração física e os serviços externos permanecem com os limites registrados no relatório.
