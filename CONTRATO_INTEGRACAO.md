# Contrato de integração — Backend → Frontend (SPI / VisãoEPI Pro)

Este documento existe porque os dois repositórios agora são trabalhados separados, cada um por um agente diferente. Ele registra **o que o backend já implementou de fato** (não uma proposta) para os pontos 1, 2 e 3 do plano de integração, servindo de referência única para os dois lados implementarem contra a mesma definição.

Use este arquivo como referência nos dois repositórios (`backend-SPI` e `Front-SPI-2026`) antes de implementar os pontos correspondentes no frontend.

**Atualização: 2026-09-10**, branch `ajustes/integracao-backend-v2`, baseada na main (`cb494af`). Esta revisão parte do contrato existente em `Front-SPI-2026`, preservando as seções de WebSocket, estatísticas e a decisão sobre coordenadas de câmera. Redis, RQ, MQTT e workers em lote permanecem na arquitetura.

**Status**: migração de Classificação aplicada ao banco configurado após autorização final, com backup completo verificado e `psql --single-transaction --set=ON_ERROR_STOP=1`. Os quatro alertas existentes foram preservados como `legado`. API e worker reiniciados com o código atualizado; oito verificações HTTP reais aprovadas. A suíte tem 52 testes aprovados, sem skips, incluindo 18 com PostgreSQL temporário, três com cliente Socket.IO local e um de criação de subprocesso Windows. Redis local permanece indisponível e as cinco câmeras estão desconectadas; entrega de e-mail, MQTT e inferência física não foram validados de ponta a ponta. Sem commit ou push; a cópia do frontend não foi alterada. Consulte o relatório para backup, execução e limites.

---

## 1. Notificação em tempo real — WebSocket

**Tecnologia**: `flask-socketio`. Isso significa que o frontend precisa de um **cliente Socket.IO** (biblioteca `socket.io-client`), e não de uma conexão `WebSocket` nativa do navegador — os dois protocolos não são compatíveis diretamente.

**Conexão**: mesmo host/porta já usado pelo `API_BASE_URL` em `api.js` (`http://localhost:5000` em dev). O `app.py` atual configura Socket.IO com `cors_allowed_origins="*"` e Redis como fila de mensagens; a antiga afirmação de restrição de origens Socket.IO em produção não corresponde à main atual. Essa configuração não foi alterada nesta rodada.

**Evento emitido**: `novo_alerta`

**Payload** (mesmo conjunto de campos nos dois caminhos de emissão):
```json
{
  "id_monitorar": 12,
  "id_usuario": 4,
  "id_camera": 1,
  "id_zona": 3,
  "nome_zona": "Entrada",
  "nome_camera": "Câmera 1",
  "nome_setor": "Produção",
  "evento": "Capacete não detectado",
  "severidade": 3,
  "tipo_deteccao": "epi"
}
```

**Pontos de atenção para o frontend**:

- **Não existe `id` do alerta no payload.** O INSERT no banco não usa `RETURNING`, então o WebSocket não informa o id do alerta recém-criado — se a tela precisar do id (ex: para linkar para o alerta específico), vai ser necessário buscar via `GET /alertas` depois de receber o evento, não dá para confiar só no payload do WebSocket.
- O evento só é emitido **depois** que o alerta foi salvo com sucesso no banco — não há emissão especulativa/antes da confirmação.
- `id_usuario` está sempre presente como inteiro ou `null`. No caminho de EPI, são mantidos os registros por responsável e uma única emissão por chamada: o campo referencia o primeiro responsável cujo registro foi salvo. Sem responsáveis, o registro e o evento usam `null`. No caminho de postura, referencia o usuário do registro único, mesmo quando há vários destinatários de e-mail. Não é uma lista de destinatários, não é a pessoa detectada e não limita quem recebe o evento global.
- Em EPI, `id_zona` é obtido de `Zona.id`; no argumento em dicionário, aceita `id` ou `id_zona`. Em postura/queda, `id_zona`, `id_monitorar` e `nome_zona` são intencionalmente `null`: a origem é a câmera diretamente. Nomes podem ser `null` quando ausentes na origem ou nas consultas relacionadas. Veja a seção 5 para o payload de Classificação.
- `tipo_deteccao` identifica explicitamente `epi`, `postura_tronco`, `postura_rotacao` ou `queda`. O frontend deve separar as telas por esse campo, sem examinar palavras do evento. `legado` é exclusivo da leitura do histórico, não é emitido pela criação de novos alertas.
- Os nomes `nome_camera`, `nome_setor` e `nome_zona` agora acompanham os campos brutos. O frontend pode utilizá-los com fallback para os IDs, mantendo a conversão de `severidade` numérica para texto e de `evento` para descrição. Não há campos chamados `sector`, `camera`, `severity` ou `description` no payload.
- **Reconexão/erro de conexão**: não foi definido nenhum comportamento específico do lado do backend (sem heartbeat customizado, sem evento de erro dedicado). O frontend deve tratar isso com o comportamento padrão do cliente Socket.IO (reconexão automática) e continuar funcionando por polling/REST enquanto o socket não estiver conectado, para não quebrar a tela se o WebSocket cair.

**E-mail**: para severidade 3, o backend enfileira tarefas RQ na fila `emails` para os responsáveis/destinatários existentes. É **inteiramente responsabilidade do backend** — o frontend não aciona esse envio diretamente. Os destinatários foram preservados; preencher `id_usuario` não cria novas emissões WebSocket nem elimina destinatários de e-mail. Se a página de configurações for expor um toggle de "receber notificação por e-mail", isso ainda não tem endpoint definido — é um item em aberto, não assumir que existe.

---

## 2. Endpoints de estatística da dashboard

### `GET /alertas/estatisticas/epi`

Contagem de alertas com `tipo_deteccao = 'epi'`, agrupados por categoria de equipamento. Exclui postura/queda e o histórico `legado`. Após a migração, os números podem diminuir ou retornar `[]` até novos alertas EPI serem registrados. Essa mudança foi aprovada pelo usuário, que comunicará o grupo. O histórico continua acessível em `/alertas?tipo=legado` e nas estatísticas por período.

```json
[
  { "categoria": "Capacete", "total": 14 },
  { "categoria": "Luvas", "total": 7 },
  { "categoria": "Óculos", "total": 3 }
]
```

Uso pretendido: substituir os dados fixos do gráfico de rosca (`dashboardPpeChart`) em `dashboard.js`.

### `GET /alertas/estatisticas/periodo`

Contagem de alertas por dia (últimos 30 dias por padrão), incluindo EPI, postura/queda e legado. Nesta entrega não há filtro de tipo nas estatísticas por período.

Parâmetro opcional: `?periodo=N`, em dias inteiros positivos. Exemplo: `GET /alertas/estatisticas/periodo?periodo=7`. Sem parâmetro, mantém 30 dias. Texto, valor vazio, zero, negativo, fracionário ou período fora do intervalo de datas suportado retornam **400**, com objeto `{"message": "..."}`. A rota converte o parâmetro para inteiro antes do serviço. Antes desta correção, `?periodo=7` provocava **500** (`TypeError` em `timedelta`); a chamada sem parâmetro já funcionava. O parâmetro implementado chama-se `periodo`, não `dias`.

Ambas as rotas de estatística retornam **200** com array, inclusive `[]` quando não há registros. A consulta por período usa um corte de N dias a partir do instante da requisição e agrupa os resultados por data.

```json
[
  { "dia": "2026-08-05", "total": 3 },
  { "dia": "2026-08-06", "total": 5 }
]
```

Uso pretendido: substituir os dados fixos do gráfico de linha (`dashboardAlertsChart`) em `dashboard.js`.

**Pontos de atenção para o frontend**:

- `categoria` pode não cobrir todas as labels que o gráfico atual mostra (`Capacete`, `Colete`, `Luvas`, `Óculos`, `Botina`) — se um tipo de EPI nunca gerou alerta, ele **simplesmente não aparece na lista**, em vez de vir com `total: 0`. O frontend precisa preencher os tipos ausentes com zero antes de passar para o Chart.js, ou o gráfico vai variar de forma inconsistente.
- `dia` vem no formato `YYYY-MM-DD` (data, sem hora) — o gráfico atual usa labels tipo `"Seg 08h"` (dia + turno); isso é uma granularidade diferente da que o mock tinha. Ajustar o eixo X do gráfico para refletir dias, não turnos, a menos que se peça ao backend para granularizar por hora também.
- Alertas sem categoria de EPI aparecem como `"Sem Categoria"`. Não normalizar silenciosamente esse grupo como um equipamento específico.

---

## 3. Câmera — mapeamento e monitoramento

### `/detections` agora exige o id da câmera

Antes: `GET /detections` (ignorava qual câmera foi pedida, sempre devolvia o último worker criado).

Agora: `GET /detections/<int:camera_id>`

O `monitoramento.js` precisa ser ajustado para passar o `camera_id` da câmera que está sendo exibida no momento, em vez de chamar `/detections` sem parâmetro.

**Formato atual: objeto, não array puro.** O frontend deve ler `data.detections` e os demais campos:

```json
{
  "detections": [
    {"id": 7, "label": "sem_capacete", "confidence": 0.94, "zona": 3}
  ],
  "class_count": {"sem_capacete": 1},
  "connected": true,
  "fps": 10.0,
  "latencia_ms": 46.0
}
```

- `detections[].id`: ID de tracking, sem garantia de identidade persistente; `label`: classe; `confidence`: confiança; `zona`: ID da zona associada.
- `class_count`: contagem por classe no frame, que pode incluir objetos ausentes de `detections`, pois a lista depende da associação a zonas.
- `connected`: processo vivo, captura conectada e último frame recebido há menos de cinco segundos.
- `fps`: frames distintos processados por segundo, por câmera. A janela contém instantes de conclusão dos últimos três segundos; com pelo menos duas amostras, calcula `(n - 1) / (agora - instante_mais_antigo)`. Com menos de duas, retorna zero. Cada frame tem uma sequência e não é processado novamente. O polling apenas lê as amostras, sem gerar medições adicionais.
- `latencia_ms`: milissegundos entre o recebimento do frame pelo backend e a preparação do resultado após EPI e postura. Inclui a espera pelo processamento em lote, mas não mede sensor, codificação JPEG, transporte HTTP ou renderização no navegador. Pode ser `null`.

`last_frame_time` é um timestamp interno de captura, atualizado após leitura bem-sucedida; não mede o fim da inferência. As métricas usam relógio monotônico e são publicadas junto das detecções em um snapshot por câmera.

| Estado | HTTP | Resposta |
| --- | --- | --- |
| Worker e resultado recente | 200 | Objeto com resultados e métricas. |
| Câmera desconectada ou processo encerrado | 200 | `detections: []`, `class_count: {}`, `connected: false`, `fps: 0`, `latencia_ms: null`. |
| Captura ativa, sem resultado ou resultado com cinco segundos ou mais | 200 | Mesmos valores vazios, mas `connected: true`. |
| Sem worker para o ID solicitado, inclusive sem nenhum worker | 503 | Objeto vazio com `connected: false` e campo adicional `message`. |

Exemplo de indisponibilidade:

```json
{
  "detections": [],
  "class_count": {},
  "connected": false,
  "fps": 0.0,
  "latencia_ms": null,
  "message": "Worker para a câmera 99 não está em execução."
}
```

A rota não consulta o cadastro para distinguir um ID inexistente de uma câmera cadastrada sem worker: ambos retornam 503. Foi eliminado o antigo retorno 200 com `{"detections": [], "zonas": []}` quando não havia workers. O frontend deve limpar indicadores antigos na indisponibilidade e continuar consultando a rota: o evento `novo_alerta` não substitui o polling de detecções.

### Câmeras online no dashboard

`GET /cameras/status` já existe e mantém HTTP 200 com array de todas as câmeras cadastradas:

```json
[
  {"id": 1, "nome": "Entrada", "ip": "rtsp://camera-exemplo/stream", "id_setor": 1, "status": "Ativo"}
]
```

Os valores são `Ativo` (processo vivo e captura recente), `Desconectado` (há worker associado, mas não satisfaz a disponibilidade) e `Inativo` (sem worker). O dashboard calcula online contando `status === "Ativo"` e total pelo tamanho do array. Sem cadastro, retorna `[]`, equivalente a `0/0`. O formato de `GET /cameras` foi preservado.

### Stream de vídeo sem mudança de contrato

`GET /video/<camera_id>` mantém URL e formato MJPEG. A afirmação histórica de que a disputa entre abas estava resolvida não foi revalidada nesta rodada: a main usa uma fila por câmera consumida pelos viewers. Não há garantia nova sobre múltiplos viewers. Sem worker, a rota responde 503.

### Coordenadas de câmera para o mapa — fora de escopo

**Decisão confirmada**: o backend não vai expor `pos_x`/`pos_y` de câmera nesta etapa. O `mapeamento.js` deve continuar usando a geração automática de grade (`generatePositions`) como está hoje — não há coordenada real disponível para consumir.

Se isso mudar no futuro, este contrato precisa ser atualizado antes do frontend alterar `mapeamento.js`.

---

## 4. Criação de zona

`POST /zonas/registrar` mantém o corpo com `nome`, `id_camera`, `x`, `y`, `largura`, `altura` e `permitido`. `id_epi`, já aceito pelo DTO, é opcional (inteiro ou `null`) e agora é gravado em `monitorar` junto da zona.

O cadastro confirma `zonas` e `monitorar` na mesma transação. Se a gravação do vínculo falhar, desfaz a zona e retorna 400. Após sucesso, mantém a invalidação de cache Redis e o sinal de recarga ao worker. Resposta 201 com os campos existentes: `id`, `nome`, coordenadas, dimensões, `permitido` e `id_camera`. IDs de câmera e EPI precisam existir. Omitir `id_epi` não cria uma exigência de EPI automaticamente.

A consulta da visão usa `JOIN monitorar`: apenas gravar `zonas` deixava o cadastro fora dessa consulta. A correção foi validada com cliente Flask, tabelas temporárias PostgreSQL, sinalização de recarga e próxima chamada de detecção simulada. Não foi testado o botão no navegador nem a câmera física. Zonas antigas sem vínculo não foram modificadas.

---

## 5. Classificação — postura e queda

### Origem e tipos

Novos alertas de Classificação ficam vinculados diretamente à câmera, inclusive quando ela não possui zonas. O ramo da avaliação de pose informa o tipo, mantendo o texto descritivo de `evento` e os limiares anteriores:

| `tipo_deteccao` | Significado | Severidade produzida pela visão |
| --- | --- | --- |
| `epi` | Fluxo existente de equipamento/zona proibida. | Regra existente do evento. |
| `postura_tronco` | Alerta de postura do tronco. | 1 |
| `postura_rotacao` | Alerta de rotação. | 1 |
| `queda` | Alerta de queda. | 3 |
| `legado` | Registro anterior à migração, sem identificação confiável da origem. | Valor histórico preservado. |

`legado` não atesta que o evento era de EPI nem de postura. Todos os registros anteriores recebem esse marcador, sem interpretar texto nem alterar seus vínculos antigos. O default `epi` vale apenas para novos INSERTs. Serviços/repositório não aceitam criar alertas do tipo `legado`.

### Listagens com filtro `tipo`

O parâmetro opcional foi adicionado às três listagens:

- `GET /alertas`
- `GET /alertas/camera/<int:camera_id>`
- `GET /alertas/zona/<int:zona_id>`

| Valor de `tipo` | Seleção |
| --- | --- |
| Ausente | Todos os tipos, incluindo legado. |
| `epi` | Apenas EPI explicitamente identificado. |
| `postura` | Grupo de `postura_tronco`, `postura_rotacao` e `queda`. |
| `postura_tronco`, `postura_rotacao` ou `queda` | Somente o subtipo informado. |
| `legado` | Somente o histórico anterior à migração. |

Exemplos: `/alertas?tipo=postura`, `/alertas?tipo=epi`, `/alertas/camera/2?tipo=queda`. Postura/queda não aparece na listagem por zona porque não tem zona associada. A consulta por câmera inclui tanto vínculos diretos de postura como a câmera derivada da zona em EPI/legado.

| Estado | HTTP | Resposta |
| --- | --- | --- |
| Listagem com resultados | 200 | Array de alertas. |
| Listagem sem resultados | 404 | Objeto com `message`, preservando o comportamento anterior. |
| Câmera/zona inexistente ou sem alertas compatíveis | 404 | Mesma mensagem de ausência de resultados da rota; não distingue esses casos. |
| `tipo` vazio, desconhecido, com espaços adicionais, caixa diferente ou repetido | 400 | `{"message":"tipo inválido; informe um dos valores permitidos."}` |
| Detalhe `/alertas/<id>` existente/inexistente | 200 / 404 | Objeto de alerta / `{"message":"Alerta não encontrado"}`. |

O filtro exige valor exato e uma única ocorrência, inclusive quando os valores repetidos são iguais. `tipo=postura` é um agrupamento de consulta, não um valor persistido. O filtro é parametrizado no SQL.

Exemplo de `GET /alertas?tipo=queda`:

```json
[
  {
    "id": 23,
    "resolvido": false,
    "data": "2026-09-10 14:30:00",
    "id_monitorar": null,
    "id_usuario": 4,
    "evento": "Alerta: Possível queda",
    "severidade": 3,
    "id_zona": null,
    "id_camera": 2,
    "id_epi": null,
    "tipo_deteccao": "queda"
  }
]
```

IDs, data e texto acima são ilustrativos. O backend mantém o motivo produzido pela avaliação. `data` conserva `YYYY-MM-DD HH:MM:SS`, sem sufixo de fuso, conforme o contrato anterior. As respostas REST mantêm seus campos anteriores e acrescentam `tipo_deteccao`; os nomes de câmera/setor/zona continuam no WebSocket, não foram acrescentados ao REST.

Em postura/queda, `id_monitorar`, `id_zona` e `id_epi` são `null` porque não se aplicam ao evento vinculado à câmera. `id_usuario` é o usuário do registro ou `null` sem responsável. Em EPI, o monitoramento permanece obrigatório; `id_epi` pode ser `null`, por exemplo em zona proibida sem equipamento associado. Em legado, os IDs originais continuam disponíveis, sem garantia de significado correto para uma antiga detecção de postura.

### WebSocket de Classificação

Evento: `novo_alerta`, no mesmo canal e com as mesmas chaves do fluxo EPI, mais `tipo_deteccao`:

```json
{
  "id_monitorar": null,
  "id_usuario": 4,
  "id_camera": 2,
  "id_zona": null,
  "nome_zona": null,
  "nome_camera": "Câmera 2",
  "nome_setor": "Produção",
  "evento": "Alerta: Possível queda",
  "severidade": 3,
  "tipo_deteccao": "queda"
}
```

O setor e seu nome são obtidos pela câmera. `nome_zona` é `null` por ausência de vínculo com zona; os demais nomes podem ser nulos se indisponíveis. Postura preserva registro único e uma emissão por chamada, com primeiro responsável ou `null` no campo `id_usuario`. Severidade 3 mantém todos os destinatários de e-mail existentes; não há disparo quando a persistência falha. O payload é emitido após o commit e continua sem ID/data do alerta.

Câmera inexistente é rejeitada na criação interna, sem INSERT nem notificação. Um vínculo inválido detectado na persistência provoca rollback e nenhuma emissão. Essas funções são internas: não foi criada uma rota HTTP de cadastro de alertas. O filtro HTTP inválido, por sua vez, responde 400 antes de consultar o serviço.

### Resolução e integração com a tela

`PUT /alertas/<id>/resolvido` permanece com 200 em sucesso e 400 em falha/ID inexistente. Postura pode ser resolvida sem monitoramento e sem buscar ou resetar um alarme arbitrário. EPI mantém `RESET` quando existe alarme associado. Não foi introduzido disparo de alarme físico para postura.

A tela de Classificação deve consumir `tipo=postura`, aceitar câmera sem zona e tratar 404 de listagem como estado vazio. A tela de EPI deve consumir `tipo=epi`. O histórico `legado` deve ter acesso identificado, sem ser apresentado como detecção confirmada de uma das categorias. No Socket.IO, separar por `tipo_deteccao` e atualizar via REST quando forem necessários ID, data ou resolução. Manter consulta REST na indisponibilidade do socket.

### Disponibilização e limites

A migração acrescenta `tipo_deteccao` e `id_camera`, torna `id_monitorar` opcional e impõe constraints: EPI/legado exigem monitoramento sem câmera direta; postura exige câmera direta sem monitoramento. A FK de câmera usa `ON DELETE RESTRICT` para preservar a origem de alertas. O script é incremental, de execução única, e deve rodar em uma transação controlada pelo chamador. O DDL de instalação foi atualizado, mas não deve ser executado sobre um banco existente.

**Aplicação no banco real concluída após autorização e backup.** A API e o worker usam o schema novo. O reinício exigiu tornar a entrada `_run_batch` estática, pois o método vinculado ao objeto tentava serializar o `multiprocessing.Manager` no Windows; o ajuste foi validado com subprocesso real. Em futuras atualizações, manter migração e reinício coordenados: workers antigos não devem gravar postura com default `epi`. A cópia deste contrato no frontend será sincronizada na rodada daquele repositório.

---

## Itens explicitamente fora deste contrato e validações pendentes

- Pool PostgreSQL: adiado por decisão do usuário após medição curta. A conexão não foi alterada. A migração de Classificação foi testada em tabelas temporárias e depois aplicada ao banco configurado, com autorização, backup e validação transacional dos dados históricos.
- Tracking e cooldown: permanecem as chaves por `track_id` com `SET NX EX 30`. `ALERT_DIAGNOSTICS=true` habilita logs JSON com horário, tipo, câmera, zona quando disponível, evento, ID de tracking e decisão da trava; padrão desativado. O teste com câmera IP ficou para 2026-09-11. Não foi decidida a remoção de `track_id` nem implementada supressão por toda a duração de um incidente.
- O frontend ainda precisa consumir o objeto de detecções, as métricas e os status. Nenhum arquivo do frontend foi alterado nesta sessão.
- O cliente de testes Socket.IO verifica serialização e recebimento local; não valida Redis entre processos. Entrega real de e-mail/RQ, MQTT, streaming, navegador e câmera continuam pendentes. Consulte `RELATORIO_AJUSTES_BACKEND_V2.md` para as evidências e limites de cada teste.
