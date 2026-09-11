# Relatório de ajustes — Backend v2

Sessão: 2026-09-10. Branch: `ajustes/integracao-backend-v2`, criada após `git fetch origin` a partir de `origin/main` (`cb494af`).

**Atualização de Classificação:** migração aplicada após autorização final, com backup verificado e quatro alertas históricos preservados. API e worker reiniciados; 52 testes e oito verificações HTTP reais aprovados. Redis local e conexão das cinco câmeras permanecem indisponíveis. A seção final registra a execução; as seções anteriores preservam as evidências e decisões de cada etapa.

## Decisões do usuário

- Usar main como base, preservando Redis, RQ, MQTT e workers em lote.
- Medir concorrência e adiar o pool PostgreSQL nesta rodada.
- Manter `track_id` nas chaves de cooldown. Validar sua estabilidade amanhã, 2026-09-11, com câmera IP disponível.
- Concluir hoje métricas, criação de zona, contrato e evidências disponíveis.
- Corrigir a ausência de `id_usuario` no WebSocket e o tipo de `periodo` antes de salvar o contrato, preservando as seções existentes.

## Implementado

### Métricas e detecções

Arquivos: `core/vision_metrics.py`, `services/visao_service.py`, `worker/vision_worker.py`, `controller/visao_routes.py`.

Cada frame capturado recebe sequência e instante monotônico. Frames já processados não voltam à inferência. A janela de três segundos guarda conclusões de processamento por câmera, sem depender do polling HTTP. O worker publica um snapshot coerente de detecções, contagem e medição.

A rota mantém resposta em objeto e acrescenta FPS de processamento e latência do recebimento do frame pelo backend até a preparação do resultado, após EPI e postura. Essa latência não mede sensor, JPEG, transporte HTTP ou navegador. `last_frame_time` permanece timestamp de captura e passou a ser atualizado depois da leitura bem-sucedida.

Resultados de câmera desconectada ou com cinco segundos sem conclusão são esvaziados. A conexão considera processo vivo e captura recente. Sem worker, a rota retorna consistentemente 503, inclusive quando a coleção de workers está vazia; antes havia um retorno 200 com campos diferentes nessa situação. O frontend ainda precisa adaptar seu parser e seus indicadores na próxima rodada.

### Câmeras online

A rota `/cameras/status` já existia na main. Foi preservada e testada com câmeras ativas, desconectadas e sem worker. O dashboard pode contar os status `Ativo` sobre o total retornado. Corrigida a anotação de retorno de `get_camera_status` para `str`.

### Criação de zonas — falha confirmada e corrigida

Arquivos: `repository/zonas_repository.py`, `services/zonas_service.py`.

O cadastro gravava somente `zonas`, mas a consulta da visão usa `JOIN monitorar`. Uma consulta somente de leitura ao banco confirmou ausência de trigger para criar o vínculo e encontrou uma zona preexistente sem monitoramento.

O cadastro agora grava a zona e o vínculo em `monitorar` na mesma transação, usando o `id_epi` que o DTO já aceitava. Falha no vínculo provoca rollback da zona. Mantidas invalidação do cache Redis e notificação ao worker após sucesso. Nenhuma migração de schema foi aplicada, e a zona antiga sem vínculo não foi modificada.

### Diagnóstico dos alertas

Arquivos: `core/alerta_diagnostics.py`, `services/visao_service.py`, `exemple.env`.

`ALERT_DIAGNOSTICS=true` habilita logs JSON dos candidatos a alerta com horário, tipo, câmera, zona quando disponível, evento, ID de tracking e resultado da trava. O padrão é desativado. O `.env` real não foi editado.

As duas chaves continuam incluindo `track_id`, com Redis `SET NX EX 30`. Não se concluiu que o ID é instável e não se removeu sua granularidade. Um cooldown de 30 segundos continua permitindo novo alerta após expirar: a supressão durante toda a ocorrência exige outra decisão, após evidência.

## Validação realizada

Resultado final após as correções adicionais: **26 testes aprovados**, em 0,905 segundo após os imports. A execução anterior, antes desses ajustes, tinha 15 testes aprovados.

- Onze testes automatizados de métricas, envelhecimento dos resultados, independência do polling, isolamento de câmeras no lote, status, contrato de indisponibilidade, diagnóstico, locks e rollback.
- Onze testes adicionais de contrato dos alertas: payload igual nos dois caminhos, referência ao usuário salvo, uma emissão para vários responsáveis, preservação dos destinatários, `null` sem responsável, ausência de emissão quando a gravação falha, suporte ao argumento em dicionário, estatísticas e validação de período. Um deles verifica recebimento por cliente Socket.IO local, substituindo apenas a distribuição via Redis.
- Quatro testes com PostgreSQL real e tabelas temporárias de sessão: zona visível na consulta da visão; EPI associado corretamente; rollback completo com EPI inválido; cadastro pela rota, sinal real de recarga e zona presente na próxima chamada de detecção simulada.
- Nos testes PostgreSQL, `search_path` foi limitado a `pg_temp`. Não foram gravados dados de negócio nas tabelas reais. Redis foi substituído por mock; captura e inferência foram simuladas.
- Checagem sintática dos arquivos Python alterados e `git diff --check`: aprovadas.
- Na primeira execução, dois testes falharam por uso de `Mock` em context managers. As fixtures foram corrigidas para `MagicMock`; a suíte final passou.

Comando de reprodução no PowerShell, com o ambiente local preparado:

```powershell
$env:YOLO_CONFIG_DIR = Join-Path (Get-Location) '.venv\ultralytics-config'
$env:RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Sem `RUN_POSTGRES_TESTS=1`, os quatro testes PostgreSQL são ignorados. Foi criado `.venv` com acesso aos pacotes já instalados e instaladas nele as dependências ausentes Redis, RQ, Flask-Session e Paho MQTT. Essas dependências já constavam em `requirements.txt`.

## Correções finais do contrato

### WebSocket `novo_alerta`

A reprodução anterior à correção, usando o serviço real com persistência e emissor substituídos por mocks, mostrou uma emissão para responsáveis `[4, 5]` sem `id_usuario` e com `id_zona: null`. A intenção documentada no código era emitir uma única notificação; não havia justificativa para omitir o campo exigido pelo contrato. A ausência foi tratada como bug de compatibilidade.

Os dois caminhos agora usam a mesma montagem de payload. No caminho com registros por responsável, `id_usuario` referencia o primeiro responsável cujo registro foi salvo; sem responsável é `null`. No caminho de registro único, mantém o usuário desse registro. Não representa a pessoa detectada nem a lista de destinatários. Registros por responsável, uma emissão por chamada e destinatários de e-mail foram preservados. Se nenhum registro for salvo, não há emissão nem e-mail.

Também foi corrigido o acesso a `id_zona`: o modelo `Zona` expõe `id`, enquanto o código anterior procurava `id_zona`. A montagem suporta `Zona` e os dicionários aceitos pela assinatura. O evento continua sem ID/data do alerta; o frontend deve consultar REST quando precisar desses dados.

### Estatísticas por período

Reprodução antes da alteração com cliente Flask e serviço real: sem parâmetro retornava 200; `?periodo=7` e `?periodo=abc` retornavam 500. Erro: `unsupported type for timedelta days component: str`. O frontend atual consulta sem parâmetro, portanto a chamada padrão de 30 dias não estava quebrada; a variante parametrizada estava.

A rota converte `periodo` para inteiro positivo. Texto, vazio, zero, negativo ou fração retornam 400 em JSON. Valores que excedem o intervalo de datas suportado também retornam 400. Mantidos default de 30 dias e resposta em array de `{dia, total}`; o endpoint de EPI mantém `{categoria, total}`.

Depois da correção, consulta pelas rotas Flask com conexão PostgreSQL real em modo somente leitura:

| Requisição | HTTP | Formato |
| --- | --- | --- |
| `/alertas/estatisticas/periodo` | 200 | Array de `dia`, `total` |
| `/alertas/estatisticas/periodo?periodo=7` | 200 | Array de `dia`, `total` |
| `/alertas/estatisticas/periodo?periodo=abc` | 400 | Objeto com `message` |
| `/alertas/estatisticas/epi` | 200 | Array de `categoria`, `total` |

### Contrato gravado

`CONTRATO_INTEGRACAO.md` foi criado no backend a partir da cópia integral existente no frontend, com alterações pontuais. Preservadas as seções de Socket.IO/`novo_alerta`, estatísticas e a decisão de não expor coordenadas de câmera (`generatePositions` mantido). Foram atualizados payload, regras de período, detecções, métricas, status, zonas e limites de validação. Corrigidas afirmações históricas que não correspondiam à main: CORS de Socket.IO restrito em produção e garantia de streaming para múltiplas abas. Nenhum código dessas duas funcionalidades foi alterado.

A gravação inicialmente recusada foi autorizada explicitamente pelo usuário nesta continuação e está concluída. A cópia no frontend permanece intacta, para sincronização na próxima rodada.

## Medição da conexão compartilhada

PostgreSQL real, 24 consultas `SELECT count(*) FROM alertas` por cenário, mesma conexão, somente leitura e autocommit. Medição curta local, sem executar carga de vídeo ou tráfego HTTP.

| Concorrência | Mediana | p95 | Tempo total |
| --- | --- | --- | --- |
| 1 | 0,18 ms | 0,53 ms | 6,76 ms |
| 4 | 0,68 ms | 1,68 ms | 6,60 ms |
| 8 | 1,07 ms | 1,18 ms | 5,37 ms |

A amostra não demonstra gargalo perceptível na aplicação completa e não compara com um pool. Mantida a conexão atual conforme decisão do usuário. Não foram alterados `connection/conn.py` nem os outros seis repositórios para introduzir pooling.

## Limites e pendências

- Câmera física: nenhuma validação de tracking ou inferência real nesta sessão. As cinco fontes cadastradas deram timeout na sondagem TCP; não foi encontrado vídeo no repositório nem câmera local na listagem do Windows.
- Redis configurado recusou conexão. O Docker daemon estava indisponível e o WSL não estava instalado. Não houve teste integrado real de Redis, RQ, entrega de e-mail, MQTT ou WebSocket.
- O botão do frontend não foi exercitado no navegador. A validação da zona cobre rota Flask, SQL PostgreSQL, sinalização e detecção simulada, sem afirmar teste visual com câmera.
- Teste do `track_id` adiado explicitamente para 2026-09-11. Manter instrumentação e comparar pessoa parada, oclusão, retorno, múltiplas pessoas e múltiplas câmeras; usar gravação apropriada para eventos de queda. Não decidir sobre remover `track_id` antes dessa evidência e da avaliação de granularidade.
- Sincronização do contrato no frontend: pendente para a rodada desse repositório. O contrato do backend foi salvo; nenhum arquivo do frontend foi modificado.

## Estado de entrega

Código e testes disponíveis na branch de ajustes. `app.py`, `extensions.py`, tarefas RQ/MQTT, eventos e `requirements.txt` permanecem iguais à main usada como base. Não houve edição direta de main, commit, push ou implantação nesta sessão.

## Classificação — postura e queda

### Por que a mudança no banco precisou ser maior

O sistema já detectava tronco, rotação e queda, mas salvava esses eventos usando a primeira zona da câmera. O vínculo podia apontar para um equipamento sem relação com o ocorrido. Além disso, sem zonas, a detecção de postura não era registrada. O texto do evento era a única pista para tentar separar EPI de postura.

Uma coluna de tipo resolveria a identificação, mas não a localização incorreta. Por isso, o usuário aprovou também a câmera diretamente no alerta e a possibilidade de não haver monitoramento. A confirmação incluiu ciência de que o gráfico de EPI excluirá o histórico sem tipo confiável.

### O que foi preparado e implementado no código

- Migração incremental `assets/migrations/001_classificacao_alertas.sql`: adiciona `tipo_deteccao` e `id_camera`, torna `id_monitorar` opcional e impõe constraints de tipo/vínculo. Deve ser executada uma única vez, dentro de transação controlada pelo chamador, com limites de espera por lock e duração de comando. O DDL de instalação também foi atualizado, sem ser executado nas tabelas reais.
- Histórico: a migração atribui `legado` aos registros existentes sem alterar seus demais campos. Depois muda o default para `epi` somente nas novas inserções. Serviços rejeitam a criação de novos eventos como legado. Não há reclassificação por palavras do evento.
- EPI mantém monitoramento e deriva a câmera da zona. Postura usa câmera diretamente e deixa monitoramento, zona e equipamento nulos. A FK de câmera usa `ON DELETE RESTRICT` para preservar a origem do alerta.
- A visão passa explicitamente `postura_tronco`, `postura_rotacao` ou `queda`; câmera sem zona passa a poder gerar alertas. Textos, geometria, limiares e severidades foram preservados, incluindo queda com severidade 3.
- Listagens geral, por câmera, zona, usuário e detalhe aceitam o novo vínculo. Consultas e serialização repetidas foram centralizadas para aplicar o mesmo tratamento a todas as leituras. Todas as respostas REST de alertas incluem `tipo_deteccao`.
- `GET /alertas`, `/alertas/camera/<id>` e `/alertas/zona/<id>` aceitam filtro `tipo`. `postura` reúne os três subtipos; os valores exatos e `legado` também podem ser consultados. Tipo inválido/vazio/repetido retorna 400; listagem sem resultado conserva 404 com mensagem.
- `novo_alerta` conserva todas as chaves anteriores e acrescenta o tipo. Em postura, câmera/setor vêm da câmera, enquanto os campos de zona/monitoramento são nulos. A emissão continua após persistência bem-sucedida, sem ID/data do alerta no socket.
- Foram preservados registros por responsável e emissão única no EPI; registro único e todos os destinatários de e-mail crítico na postura; `id_usuario` presente, inclusive como `null` sem responsável. Falha de INSERT faz rollback e não emite notificação.
- Resolver postura não tenta acessar um monitoramento inexistente nem resetar alarme arbitrário. EPI conserva RESET quando há alarme; ID de alerta inexistente responde falha controlada, sem 500 por acesso a `None`.

### Impacto no dashboard e trabalho do frontend

`/alertas/estatisticas/epi` passa a contar somente tipo `epi`, excluindo postura e legado. Os números serão menores, podendo ficar vazios imediatamente após a migração até surgirem novos eventos de EPI. Os dados antigos não são apagados: continuam em `/alertas?tipo=legado`, na consulta sem filtro e nas estatísticas por período. O usuário confirmou esse comportamento e avisará o grupo.

O frontend ainda precisa consumir `tipo=postura` para Classificação e `tipo=epi` para EPI; separar eventos Socket.IO pelo campo estruturado; aceitar zona/equipamento nulos; tratar 404 das listagens como estado vazio; e oferecer acesso identificado ao legado. Para ID, data e estado de resolução, deve consultar REST. A cópia do contrato no frontend ainda precisa ser sincronizada na rodada daquele repositório. Nenhum arquivo do frontend foi alterado.

### Evidências desta continuação

**51 testes aprovados, zero falhas/erros e zero skips**, em 3,190 segundos após os imports. São os 26 testes anteriores, adaptados onde o payload/assinatura mudou, mais 25 testes de Classificação. Ao todo, 18 usam PostgreSQL real com tabelas temporárias da sessão: os quatro de zonas e 14 novos. Três testes usam cliente Socket.IO local; um deles associa INSERT real, commit e recebimento do evento.

Os testes cobrem conservação de todas as colunas históricas, defaults, constraints, falha e rollback de toda a migração, rejeição de reaplicação, equivalência dos CHECKs entre instalação e migração, filtros e HTTP, consulta por câmera/zona/usuário/detalhe, estatísticas, câmera sem zona, câmera/zona/monitoramento/usuário inexistentes, tipos inválidos e resolução com/sem alarme. Os três ramos da visão foram exercitados com o mesmo texto de evento para verificar que o tipo não depende do texto. Tracking ausente continua sem gerar alerta.

Toda gravação de teste usa tabelas `TEMP` e `search_path=pg_temp`. O teste de instalação remove os comandos DROP do DDL antes de criar sua versão temporária; o teste de rollback recria somente `pg_temp.alertas`. A aplicação não foi iniciada contra o banco real. Socket.IO distribuído, filas de e-mail e comandos MQTT foram substituídos por clientes locais/mocks; não foram enviados e-mails nem acionados equipamentos.

A primeira rodada encontrou cinco erros nas fixtures: nomes obrigatórios de zonas, mock sem `len`, credenciais da segunda conexão e variante de exceção de restrição PostgreSQL. A segunda detectou que o mock de keypoints ainda tinha comprimento zero. Essas fixtures foram corrigidas, e a terceira rodada passou integralmente. Não foram removidos testes para obter o resultado.

Checagem sintática via AST e `git diff --check`: aprovadas. A consulta somente de leitura ao catálogo, antes e depois dos testes, confirmou que o banco de negócio continua com os quatro alertas e o schema original: sem `tipo_deteccao`/`id_camera`, com `id_monitorar` obrigatório. Nenhum dado desse banco foi migrado nesta etapa.

Reprodução da suíte no PowerShell:

```powershell
$env:YOLO_CONFIG_DIR = Join-Path (Get-Location) '.venv\ultralytics-config'
$env:RUN_POSTGRES_TESTS = '1'
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Artefatos locais de revisão, fora do versionamento:

- [Diff da Classificação](.venv/classificacao-review/CLASSIFICACAO.diff), comparado ao estado local anterior a esta implementação, incluindo arquivos novos. Assim, o diff mostra esta entrega sem atribuir a ela os ajustes anteriores da branch.
- [Saída completa dos testes](.venv/classificacao-review/tests.txt).

### Estado apresentado para revisão, antes da autorização final

**A migração não foi aplicada ao banco real.** O usuário pediu expressamente para revisar o diff e o resultado dos testes antes de autorizar essa etapa. Código e SQL estão preparados na branch `ajustes/integracao-backend-v2`; não houve commit, push, implantação ou edição do `.env`.

Depois dessa autorização, conferir novamente o schema e preparar backup, interromper gravações de API/workers, executar somente o script incremental dentro de uma transação, verificar conservação dos dados e então confirmar. Com `psql`, a execução deverá usar `--single-transaction --set=ON_ERROR_STOP=1 --file=assets/migrations/001_classificacao_alertas.sql`; as credenciais devem vir do ambiente/conexão configurada, sem entrar no comando ou no repositório. A alternativa Python usa `autocommit=False` e commit somente depois da validação, ou rollback em erro.

O código novo exige o schema novo: reiniciar API/workers de forma coordenada após a migração. Não retomar workers antigos que possam gravar postura com o default EPI. Após surgirem alertas sem monitoramento, não remover as colunas nem restaurar `NOT NULL` como um downgrade automático; qualquer recuperação precisa preservar esses dados.

`track_id`, as duas chaves Redis e `SET NX EX 30` não foram alterados. A decisão sobre duplicidade continua pendente de câmera IP. Redis entre processos, entrega real de e-mail, MQTT, navegador e inferência física seguem sem validação de ponta a ponta. Não foram alterados os modelos YOLO, métricas, coordenadas de câmera, pool PostgreSQL ou arquitetura dos workers.

### Aplicação autorizada e reinício — execução concluída

Após revisar a entrega, o usuário autorizou a aplicação com a sequência parar → migrar → atualizar código → reiniciar e exigiu `--single-transaction --set=ON_ERROR_STOP=1`.

**Backup confirmado.** Foi gerado um backup completo do banco com `pg_dump` 18, em formato custom, com 21.227 bytes. A verificação usou `pg_restore --list`, extração do schema e extração dos dados de `public.alertas`, confirmando os quatro registros. Foi calculado SHA-256 do arquivo, sem colocar credenciais em argumentos ou arquivos versionados. Essa verificação comprova leitura do arquivo; não foi feito um ensaio de restauração integral em outro banco.

- [Backup completo](.venv/classificacao-review/backups/20260911T022111Z/before-classificacao.dump).
- [Manifesto com hashes, horários e verificações](.venv/classificacao-review/backups/20260911T022111Z/manifest.json).
- SHA-256 do backup: `c35c3d97eba42a0fe628c708af1511f09cc14d31954e8594e160fbfb8a82fba0`.

Os arquivos de backup e validação estão em `.venv`, ignorados pelo Git, e contêm dados do banco. O manifesto e a saída do `psql` registram os horários UTC; a aplicação ocorreu na noite de 2026-09-10 no horário local.

**Parada.** A inspeção confirmou que API e workers já estavam parados e não havia outra sessão conectada ao banco. Essa condição foi conferida novamente antes da migração; nenhum processo de outro projeto foi encerrado.

**Migração.** Foi executado `psql` 18 com `--no-psqlrc --single-transaction --set=ON_ERROR_STOP=1`, selecionando `public`, lendo `001_classificacao_alertas.sql` e depois uma validação SQL dos dados históricos na mesma transação. O retorno foi zero. A validação compara ID, resolução, data, monitoramento, usuário, evento e severidade com o snapshot anterior, e rejeitaria o commit se qualquer campo tivesse mudado ou se o histórico não estivesse como legado. A comparação foi repetida após o reinício e permaneceu igual.

O banco agora contém `tipo_deteccao NOT NULL DEFAULT 'epi'`, `id_camera` opcional com FK RESTRICT, `id_monitorar` opcional e os dois CHECKs aprovados. Os quatro alertas preexistentes são `legado`; nenhum alerta foi excluído ou reclassificado por texto. [Saída do psql](.venv/classificacao-review/backups/20260911T022111Z/migration-output.txt).

**Código e reinício.** O código aprovado já estava preparado na branch `ajustes/integracao-backend-v2`. A primeira tentativa de reinício revelou `TypeError: cannot pickle 'weakref.ReferenceType' object`: no Windows, usar o método vinculado `self._run_batch` como entrada do processo fazia o `spawn` tentar serializar também o objeto `Manager`. A função não usa `self`; torná-la `@staticmethod` em `worker/vision_worker.py` removeu essa dependência sem mudar o trabalho do lote, seus argumentos, Redis, métricas ou cooldown.

Foi acrescentado um teste que envia a entrada real do worker a um subprocesso `spawn`, substituindo somente conexão/captura/inferência dentro do filho. A suíte completa passou com **52 testes, zero falhas/erros e zero skips**, em 15,236 segundos após imports. [Saída dos testes após a migração](.venv/classificacao-review/tests-after-migration.txt). O código também passou na checagem sintática e de whitespace.

A segunda inicialização manteve a API em `http://127.0.0.1:5000` e o worker do lote `[1, 2, 3, 4, 5]` ativos. A inspeção posterior confirmou os processos da API, Manager e worker vivos. Foram aprovadas oito verificações HTTP reais, somente de leitura:

| Consulta | Resultado |
| --- | --- |
| `/alertas` e `/alertas?tipo=legado` | 200, quatro registros do tipo legado. |
| `/alertas?tipo=postura` e `/alertas?tipo=epi` | 404, sem registros novos dessas categorias. |
| `/alertas?tipo=invalido` | 400. |
| `/alertas/estatisticas/epi` | 200 com `[]`, conforme o impacto aprovado. |
| `/alertas/estatisticas/periodo` | 200. |
| `/cameras/status` | 200, cinco câmeras desconectadas. |

[Resultados HTTP](.venv/classificacao-review/post-migration-smoke.json).

**Limites após o reinício.** Os processos foram reiniciados, mas nenhuma câmera entregou imagem: as conexões RTSP deram timeout. Redis em `localhost:6379` também não respondeu. Foi tentado iniciar o Docker Desktop já instalado para recuperar essa dependência, mas a inicialização excedeu o tempo limite; o WSL não está instalado. Não houve instalação de WSL, Redis ou alteração de configuração do sistema para contornar isso. Sem Redis/câmera, não se afirma validação de cooldown, detecção, Socket.IO distribuído ou entrega de e-mail de ponta a ponta. O teste físico de `track_id` continua pendente.

O `.env` foi preservado, não houve commit ou push e o frontend não foi alterado. A migração não deve ser executada novamente.
