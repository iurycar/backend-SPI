# SPI — Backend (VisãoEPI Pro)

Backend do Challenge FIAP 2026 em parceria com a SPI. Responsável por autenticação e gestão de usuários, inventário de EPIs, cadastro de setores, câmeras e zonas, registro e consulta de alertas, estatísticas de conformidade, integração com alarme físico (ESP32 via MQTT) e pelo pipeline de visão computacional em tempo real (YOLO + OpenCV) com captura de amostras para Active Learning e uma tela de curadoria de dataset.

Stack: **Flask** (REST + `Flask-SocketIO`), **PostgreSQL** (acesso via `psycopg2`, SQL escrito à mão), **Redis** (sessões via `Flask-Session`, cache de zonas, travas de deduplicação de alertas, buffers de estatística, fila RQ de e-mails e *message queue* do Socket.IO), **OpenCV** + **Ultralytics YOLO** (detecção de EPI e estimativa de pose) e **paho-mqtt** (alarme ESP32).

## Funcionamento do sistema

Arquitetura em camadas (Controller → Service → Repository → Model), com o processamento de visão isolado em processos separados.

1. **API (`controller/`)** — Blueprints Flask registrados em `app.py`. A autenticação é por sessão de servidor persistida no Redis; a autorização usa os decoradores `login_required` e `perfil_required` de `core/auth.py`.
2. **Regras de negócio (`services/`)** — validam a entrada através dos DTOs de `schemas/`, orquestram repositórios, invalidam cache no Redis e disparam notificações.
3. **Persistência (`repository/` + `connection/`)** — uma conexão `psycopg2` por instância de `Connection`, com queries SQL explícitas.
4. **Visão computacional (`worker/`)** — ao iniciar `app.py`, o `VisionManager` agrupa as câmeras cadastradas em **lotes** (`tamanho_lote=6` por padrão) e cria um `multiprocessing.Process` (`VisionWorker`) por lote. Dentro do processo, uma *thread* de captura por câmera lê os frames (RTSP ou webcam local) e o laço principal roda a inferência YOLO em lote sobre os frames disponíveis.
5. **Alertas** — ao detectar violação, o serviço adquire uma trava no Redis (`SET NX EX`) para não inundar o banco com o mesmo evento, grava o alerta no PostgreSQL, emite o evento Socket.IO `novo_alerta` e, quando a severidade é 3, enfileira e-mail crítico (RQ) e publica comando MQTT no alarme, se houver um associado à zona.
6. **Alarme ESP32** — comandos `DISPARAR` e `RESET` são publicados em `alarme/<endereco_esp32>/comando`.

## Estrutura principal

| Caminho | Conteúdo |
| --- | --- |
| `app.py` | Cria o app Flask, configura sessão Redis, cookies, CORS, Socket.IO, registra os Blueprints e inicia os workers de visão. |
| `controller/` | Rotas HTTP por domínio: `usuario_routes`, `cameras_routes`, `setores_routes`, `zonas_routes`, `epi_routes`, `alertas_routes`, `estatisticas_routes`, `visao_routes`, `curadoria_routes`. |
| `services/` | Regras de negócio. Inclui `visao_service.py` (todo o pipeline de detecção, pose, zonas, Active Learning e desenho do HUD), `curadoria_service.py` e `augmentation_service.py`. |
| `repository/` | Acesso ao PostgreSQL com SQL explícito (um repositório por entidade + `monitoramento_repository`). |
| `schemas/` | DTOs de validação de entrada: `usuario_dto` (`LoginDTO`, `SignupDTO`, `UsuarioDTO`), `camera_dto`, `zona_dto`, `epi_dto`, `setor_dto`, `config_dto`, `intervalo_dto`. |
| `models/` | Dataclasses das entidades (`Usuario`, `Camera`, `Setor`, `Zona`, `Epi`, `Alerta`, monitoramento). |
| `core/` | `auth.py` (decoradores de sessão/perfil), `security.py` (bcrypt), `errors.py`, `tipo_deteccao.py` (tipos de alerta), `vision_metrics.py` (FPS/latência), `alerta_diagnostics.py` (log opcional). |
| `worker/` | `vision_manager.py` (registro global de workers e notificações) e `vision_worker.py` (processo, filas de frame e estado compartilhado). |
| `events/` | `alertas_events.py`: handlers `connect`/`disconnect` do Socket.IO e entrada nas salas de setor. |
| `tasks/` | `email_task.py` (SMTP Gmail, executado pela fila RQ `emails`) e `alarme_task.py` (publicação MQTT). |
| `extensions.py` | Instância do `SocketIO`, cliente Redis e helpers `emitir_evento_global` / `emitir_evento_setor`. |
| `templates/` | `curadoria.html`, a interface de curadoria de dataset servida em `GET /curadoria`. |
| `static/js/` | JS da tela de curadoria (`api.js`, `canvas.js`, `main.js`, `sidebar.js`, `state.js`). |
| `assets/` | Scripts SQL (`tabelas_spi-postgres.sql`, `inserções_spi-postgres.sql`), modelagem `.mwb`, `config.yaml` (curadoria) e `modelo/` com os pesos YOLO e os diretórios de Active Learning. |

## Requisitos

- Python 3.10 ou superior (o código usa sintaxe `X | Y` de tipos).
- PostgreSQL 12 ou superior.
- Redis (Linux) ou Memurai (Windows) — **obrigatório**: sessão, cache, deduplicação de alertas, estatísticas, fila de e-mails e Socket.IO dependem dele.
- Broker MQTT (ex.: Mosquitto), somente se o alarme físico ESP32 for usado.
- Pesos YOLO em `assets/modelo/treinamento/`:
  - `best.pt` — modelo de detecção de EPI (versionado no repositório);
  - `yolov8m-pose.pt` — modelo de pose, exigido por `_ensure_models_loaded()`. **Não está versionado** (está no `.gitignore`); baixe-o para essa pasta antes de subir os workers.
- Dependências de `requirements.txt` (Flask, flask-cors, flask-socketio, flask-session, bcrypt, numpy, python-dotenv, psycopg2-binary, opencv-python 4.10.0.84, ultralytics, redis, rq, simple-websocket, paho-mqtt, pyyaml, albumentations).

## Instalação

1. Ambiente virtual:

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

2. Dependências:

```bash
pip install -r requirements.txt
```

3. Banco de dados:
   - Crie o banco (ex.: `spi_database`).
   - Execute `assets/tabelas_spi-postgres.sql` para criar as tabelas.
   - Opcionalmente execute `assets/inserções_spi-postgres.sql` para dados iniciais.
   - Observação: `tabelas_spi-postgres.sql` está com erro de sintaxe na definição de `zonas` (falta a vírgula antes de `CONSTRAINT chk_zonas_limites`). Corrija ao aplicar o script, ou as tabelas dependentes de `zonas` não serão criadas.

4. Variáveis de ambiente — copie o modelo e edite:

```bash
cp exemple.env .env
```

5. Geração de uma `SECRET_KEY` aleatória (opcional):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Nunca comite o `.env` nem valores reais de senha, token ou credencial. O `exemple.env` deve conter apenas *placeholders*.

## Configuração

Variáveis lidas pelo código (`app.py`, `connection/conn.py`, `extensions.py`, `tasks/`, `core/alerta_diagnostics.py`):

| Variável | Uso |
| --- | --- |
| `SECRET_KEY` | Assinatura do cookie de sessão Flask. |
| `DEV_INSECURE` | `true` libera CORS para qualquer origem e afrouxa os cookies (`HttpOnly=False`, `Secure=False`). Qualquer outro valor mantém `HttpOnly`/`Secure` ativos e o CORS restrito. |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, `DB_PASSWORD` | Conexão PostgreSQL. |
| `REDIS_URL` | Conexão Redis (padrão `redis://localhost:6379/0`). |
| `BROKER_ADDRESS`, `BROKER_PORT` | Broker MQTT do alarme (padrões `localhost` e `1883`). |
| `EMAIL_ADDRESS`, `EMAIL_PASSWORD` | Remetente SMTP (`smtp.gmail.com:587`) dos e-mails de alerta crítico. Sem eles, a tarefa registra a falta e não envia. |
| `ALERT_DIAGNOSTICS` | `true` imprime, em JSON, cada candidato a alerta e se a trava de cooldown foi adquirida. Diagnóstico apenas; não altera a política de deduplicação. |

Configurações de sessão fixadas em `app.py`: sessão do tipo `redis`, permanente, com cookie assinado e `PERMANENT_SESSION_LIFETIME` de **30 minutos**.

Configuração da curadoria: `assets/config.yaml` define `path_captured`, `path_cured` e o mapa `classes` (13 classes do modelo). Caminhos vazios ou inexistentes caem nos padrões `assets/modelo/active_learning/dataset_captura` e `assets/modelo/active_learning/dataset_tratado`.

## Execução

1. Garanta PostgreSQL e Redis/Memurai em execução (e o broker MQTT, se aplicável).
2. Inicie o backend:

```bash
python app.py
```

O servidor sobe com `socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)`. Na inicialização, todas as câmeras cadastradas são lidas do banco e agrupadas em workers de visão com `tamanho_lote=6`; `parar_vision_workers` é registrado em `atexit`.

3. Para que os e-mails de alerta crítico realmente saiam, execute um worker RQ da fila `emails` em paralelo (o backend apenas enfileira):

```bash
rq worker emails --url "$REDIS_URL"
```

## Autenticação e sessão

A autenticação é por **sessão de servidor**: o cliente recebe um cookie de sessão assinado e os dados ficam no Redis. Todas as requisições do frontend precisam enviar credenciais (`credentials: 'include'` no `fetch`).

- `POST /login` — corpo `{"email": "...", "password": "..."}`. Valida via `LoginDTO` (e-mail normalizado para minúsculas) e confere a senha com bcrypt. Em caso de sucesso popula a sessão (`user_id`, `user_email`, `user_perfil`, `user_nome`, `user_sobrenome`, `user_unidade`, `user_telefone`, `user_admin`, `user_ativo`, `user_acesso`), atualiza a coluna `acesso` do usuário e devolve `200` com o objeto `user`. Credenciais inválidas → `401`; payload inválido → `400`.
- `GET /session` — sem sessão retorna `401`; com sessão retorna `200` com `{"authenticated": true, "user": {...}}`. Usado pelo frontend para revalidar a sessão após recarregar a página.
- `POST /logout` — `session.clear()` e `200`. Não exige autenticação prévia.

**Perfis.** O campo `perfil` é texto livre no banco (`VARCHAR(20)`). Os valores efetivamente reconhecidos pelo código são:

- `admin` (ou `administrador`) — `Usuario.is_admin()` retorna verdadeiro; acessa tudo.
- `supervisor` — libera as rotas declaradas com `@perfil_required('admin', 'supervisor')`.
- Qualquer outro perfil (ex.: `operador`) só acessa as rotas protegidas apenas por `@login_required`.

`perfil_required` também autoriza quando `session['user_admin']` é verdadeiro, independentemente dos perfis listados na rota.

## Principais APIs

Todas as rotas abaixo exigem sessão ativa, salvo indicação contrária. Códigos de erro comuns: `401` sem sessão, `403` perfil insuficiente, `404` recurso não encontrado, `400` payload/parâmetro inválido.

### Usuários e autenticação

| Método | Rota | Permissão |
| --- | --- | --- |
| `POST` | `/login` | pública |
| `POST` | `/logout` | pública |
| `GET` | `/session` | pública (responde `401` sem sessão) |
| `POST` | `/signup` | admin |
| `GET` | `/users` | admin |
| `GET` | `/users/ativos` | admin |
| `PUT` | `/users/<int:usuario_id>` | admin |
| `DELETE` | `/users/<int:usuario_id>` | admin |

`POST /signup` espera `email`, `password`, `nome`, `sobrenome`, `perfil` e, opcionalmente, `unidade` e `telefone`; a senha é gravada com bcrypt (custo 12). `PUT /users/<id>` valida o corpo com `UsuarioDTO`, que exige `id`, `nome`, `sobrenome`, `email`, `senha` e `perfil` (veja as limitações conhecidas sobre esta rota).

### Setores

| Método | Rota | Permissão |
| --- | --- | --- |
| `GET` | `/setores` | autenticado |
| `GET` | `/setores/<int:setor_id>` | autenticado |
| `GET` | `/setores/responsavel/<int:usuario_id>` | autenticado |
| `POST` | `/setores/registrar` | admin ou supervisor |
| `PUT` | `/setores/<int:setor_id>` | admin ou supervisor |
| `DELETE` | `/setores/<int:setor_id>` | admin ou supervisor |

### Câmeras

| Método | Rota | Permissão |
| --- | --- | --- |
| `GET` | `/cameras` | autenticado |
| `GET` | `/cameras/<int:camera_id>` | autenticado |
| `GET` | `/cameras/setor/<int:setor_id>` | autenticado |
| `GET` | `/cameras/<int:camera_id>/zonas` | autenticado |
| `GET` | `/cameras/status` | autenticado |
| `POST` | `/cameras/registrar` | admin ou supervisor |
| `PUT` | `/cameras/<int:camera_id>` | admin ou supervisor |
| `DELETE` | `/cameras/<int:camera_id>` | admin ou supervisor |

### Zonas

| Método | Rota | Permissão |
| --- | --- | --- |
| `GET` | `/zonas` | autenticado |
| `GET` | `/zonas/<int:zona_id>` | autenticado |
| `GET` | `/zonas/camera/<int:camera_id>` | autenticado |
| `POST` | `/zonas/registrar` | autenticado |
| `PUT` | `/zonas/<int:zona_id>` | autenticado |
| `DELETE` | `/zonas/<int:zona_id>` | autenticado |

### EPIs

| Método | Rota | Permissão |
| --- | --- | --- |
| `GET` | `/epis` | autenticado |
| `GET` | `/epis/<int:epi_id>` | autenticado |
| `POST` | `/epis` | admin ou supervisor |
| `PUT` | `/epis/<int:epi_id>` | admin ou supervisor |
| `DELETE` | `/epis/<int:epi_id>` | admin ou supervisor |

Corpo de EPI (`EpiDTO`, todos obrigatórios): `nome`, `categoria`, `certificado`, `validade` (string), `estoque`, `quantidade_min`, `em_uso`.

### Alertas e estatísticas

| Método | Rota | Permissão |
| --- | --- | --- |
| `GET` | `/alertas` | autenticado |
| `GET` | `/alertas/<int:alerta_id>` | autenticado |
| `GET` | `/alertas/camera/<int:camera_id>` | autenticado |
| `GET` | `/alertas/zona/<int:zona_id>` | autenticado |
| `PUT` | `/alertas/<int:alerta_id>/resolvido` | autenticado |
| `DELETE` | `/alertas/<int:alerta_id>` | autenticado |
| `GET` | `/alertas/estatisticas/epi` | autenticado |
| `GET` | `/alertas/estatisticas/periodo` | autenticado |
| `GET` | `/estatisticas/conformidade` | autenticado |
| `GET` | `/estatisticas/setor/<int:setor_id>` | autenticado |

- As três listagens de alertas aceitam o parâmetro opcional `?tipo=`, com um único valor entre `epi`, `postura_tronco`, `postura_rotacao`, `queda`, `legado` e `postura` (este último expande para os três tipos de postura). Valor inválido ou repetido → `400`. Listagem vazia responde `404`.
- Cada alerta retorna `id`, `resolvido`, `data`, `id_monitorar`, `id_usuario`, `evento`, `severidade`, `id_zona`, `id_camera`, `id_epi`, `tipo_deteccao`.
- `PUT /alertas/<id>/resolvido` marca como resolvido e, se a zona do alerta tiver alarme associado, publica `RESET` via MQTT.
- `/alertas/estatisticas/periodo` aceita `?periodo=<dias>` (padrão `30`, inteiro positivo).
- `/estatisticas/conformidade` e `/estatisticas/setor/<id>` aceitam `?data_inicio=` e `?data_fim=` (`IntervaloDTO`); sem parâmetros, o intervalo padrão são os últimos 30 dias.

### Visão computacional

| Método | Rota | Permissão |
| --- | --- | --- |
| `GET` | `/video`, `/video/`, `/video/<int:camera_id>` | autenticado |
| `GET` | `/detections/<int:camera_id>` | autenticado |
| `POST` | `/active-learning/toggle` | admin ou supervisor |
| `POST` | `/video/lote/<int:tamanho_lote>` | admin |

### Curadoria / Active Learning

| Método | Rota | Permissão |
| --- | --- | --- |
| `GET` | `/curadoria` | autenticado (HTML) |
| `GET` | `/curadoria/favicon.png` | pública |
| `GET` | `/api/config` | autenticado |
| `POST` | `/api/config` | admin |
| `GET` | `/api/classes` | autenticado |
| `GET` | `/api/samples/count` | autenticado |
| `GET` | `/api/samples` | autenticado |
| `GET` | `/api/image/<filename>` | autenticado |
| `GET` | `/api/labels/<filename>` | autenticado |
| `POST` | `/api/save-and-move` | autenticado |
| `DELETE` | `/api/sample/<base_name>` | autenticado |

## Câmeras

Campos persistidos na tabela `cameras` e devolvidos pela API (`id`, `nome`, `ip`, `id_setor`, `rotacao`, `espelhar_horizontal`, `espelhar_vertical`):

- `nome` — opcional; `CameraDTO` usa `"Sem nome definido"` quando ausente.
- `ip` — string não vazia de até 255 caracteres, **única** no banco. É o endereço da fonte de vídeo e aceita dois formatos reconhecidos por `VisaoService.open_camera`:
  - `rtsp://...` — aberto via FFmpeg forçando transporte TCP, com *timeouts* de 5 s e `BUFFERSIZE=1`;
  - `local-webcam:<índice>` — webcam local, com backend por plataforma (`CAP_DSHOW` no Windows, `CAP_V4L2` no Linux, `CAP_ANY` nos demais).

  Qualquer outro formato não é aberto pelo worker.
- `id_setor` — inteiro obrigatório, referencia `setores`.
- `rotacao` — inteiro restrito a `0`, `90`, `180` ou `270` pelo DTO. Aplicado no frame com `cv2.rotate` (sentido horário).
- `espelhar_horizontal` / `espelhar_vertical` — booleanos, aplicados com `cv2.flip` (`1`, `0` ou `-1` quando ambos estão ativos).

As transformações são aplicadas a cada frame capturado, **antes** da inferência, em `aplicar_transformacoes_frame`, que lê os valores da câmera no banco a cada chamada.

`POST /cameras/registrar` e `PUT /cameras/<id>` notificam o worker responsável (`notificar_atualizacao_camera`), que reinicia o processo com a nova configuração; `DELETE /cameras/<id>` chama `notificar_desligamento_camera`, removendo a câmera do registro de workers.

`GET /cameras/status` devolve, para cada câmera, `id`, `nome`, `ip`, `id_setor` e `status`:

- `Ativo` — existe worker e a câmera recebeu frame nos últimos 5 s;
- `Desconectado` — existe worker, mas sem frame recente;
- `Inativo` — não há worker registrado para a câmera.

## Zonas

Zonas são retângulos **normalizados** sobre a imagem da câmera. O corpo aceito por `ZonaDTO` é:

```json
{
  "nome": "Bancada de solda",
  "id_camera": 1,
  "x": 0.1,
  "y": 0.2,
  "largura": 0.4,
  "altura": 0.5,
  "permitido": true,
  "ids_epis": [1, 3]
}
```

- `id_camera` é obrigatório e inteiro; `nome` pode ser `null`.
- `x`, `y`, `largura`, `altura` são números; os padrões são `0.0`, `0.0`, `1.0`, `1.0`. A tabela `zonas` impõe `CHECK` de `0.0 ≤ x,y ≤ 1.0`, `largura`/`altura` em `(0.0, 1.0]` e `x + largura ≤ 1.0`, `y + altura ≤ 1.0`.
- `permitido` (booleano, padrão `true`) define a semântica da zona: `true` = zona em que a presença é permitida desde que os EPIs exigidos estejam presentes; `false` = zona restrita, em que a simples presença de pessoa gera alerta de severidade 3.
- `ids_epis` é uma **lista de inteiros** e suporta múltiplos EPIs por zona: cada ID vira uma linha em `monitorar` (duplicatas são removidas). Quando a lista está vazia ou ausente, é criada uma linha `monitorar` com `id_epi = NULL` (zona sem EPI associado).

Operações:

- `POST /zonas/registrar` — cria a zona, insere os vínculos em `monitorar`, invalida o cache Redis `cache:zonas:camera:<id>` e notifica o worker (`notificar_atualizacao_zonas`) para recarregar as zonas. Retorna `201`.
- `GET /zonas`, `GET /zonas/<id>`, `GET /zonas/camera/<camera_id>` — leitura. A listagem por câmera é cacheada no Redis por 1 hora.
- `PUT /zonas/<id>` — atualiza a geometria e, quando `ids_epis` é informado, substitui todos os vínculos da zona (`DELETE` + `INSERT`). Também invalida o cache e notifica o worker.
- `DELETE /zonas/<id>` — implementada; remove a zona (os registros de `monitorar` caem por `ON DELETE CASCADE`) e notifica o worker. Veja as limitações conhecidas: a implementação atual da camada de serviço falha nesta rota.

**Resposta.** As leituras e escritas devolvem `epis_categoria`, uma lista com as **categorias** dos EPIs vinculados (agregadas por SQL a partir de `monitorar` + `epis`) — e não os `ids_epis` enviados. Não existe rota que devolva os IDs dos EPIs de uma zona.

## Visão computacional

### `GET /video/<camera_id>`

Stream MJPEG (`multipart/x-mixed-replace; boundary=frame`) do último frame processado da câmera, já com as transformações, caixas de detecção e esqueleto de pose desenhados. `/video` e `/video/` sem ID usam `camera_id=1`. Se não houver worker registrado para o ID, responde `503`.

### `GET /detections/<camera_id>`

Snapshot JSON do último resultado da câmera:

```json
{
  "detections": [{"id": 12, "label": "sem_capacete", "confidence": 0.81, "zona": 3}],
  "class_count": {"pessoa": 2, "sem_capacete": 1},
  "connected": true,
  "fps": 8.4,
  "latencia_ms": 118.5
}
```

`fps` é o FPS de processamento medido em janela de 3 s e `latencia_ms` o tempo entre captura e conclusão da inferência. Resultados com mais de 5 s são descartados e o snapshot volta zerado. Sem worker registrado, responde `503` com o snapshot vazio mais o campo `message`.

### Funcionamento dos workers

- O `VisionManager` mantém o dicionário global `workers: {camera_id: VisionWorker}`. Câmeras são fatiadas em lotes de `tamanho_lote` e cada lote recebe um processo.
- Dentro do processo, `run_batch_video_loop` cria **uma thread de captura por câmera** (para que o timeout de uma câmera não bloqueie as outras) e um laço principal que agrupa os frames novos e roda duas inferências por ciclo: `_batch_object_detection` (detecção/tracking de EPI, `conf=0.3` no tracker ByteTrack e `conf ≥ 0.5` para uso da detecção) e `_batch_pose_estimation` (pose, `conf=0.5`).
- **Reconexão de câmera**: quando `cap` não está aberto, a thread tenta reabrir no máximo a cada 5 s; se a leitura de um frame falha, o `cap` é liberado e a próxima tentativa é agendada para 4 s depois. Em ambos os casos a câmera é marcada como `connected = False`, o que reflete em `/cameras/status` e em `/detections/<id>`.
- **Transformações aplicadas**: rotação ortogonal (`90`/`180`/`270`; outros ângulos caem num fallback com `warpAffine`) seguida de espelhamento horizontal e/ou vertical. São aplicadas ao frame bruto, antes da inferência e antes da cópia usada para Active Learning.
- **Zonas**: recarregadas sob demanda via `mp.Event` por câmera (sinalizado pelas rotas de zona e de câmera). Zonas sem EPI vinculado recebem a categoria implícita `pessoa`.
- **Alertas de EPI**: gerados quando uma detecção `sem_*` intersecta uma zona que exige aquela categoria (severidade 2), quando o equipamento é inadequado (`*_normal`, severidade 1) ou quando há pessoa em zona restrita (severidade 3). Deduplicação por trava Redis de 30 s na chave `lock:alerta:epi:<id_monitorar>:<evento>:<track_id>`.
- **Alertas de postura**: `_batch_pose_estimation` avalia inclinação de tronco, torção (rotação) e queda. O alerta só é emitido se a condição persistir (10 s para tronco e rotação, 3 s para queda) e é silenciado por 45 s depois de emitido. Tipos gravados: `postura_tronco`, `postura_rotacao`, `queda`.
- **Estatísticas**: cada detecção conforme/não conforme incrementa contadores no Redis (amostragem limitada a uma por `track_id` a cada 10 s) e são gravadas em lote na tabela `estatisticas` a cada 60 s, além de um flush forçado ao encerrar o laço.

## Lote de workers — `POST /video/lote/<int:tamanho_lote>`

Comportamento atual, conforme `controller/visao_routes.py` e `worker/vision_manager.py`:

1. Exige perfil **admin** (`@perfil_required('admin')`).
2. Valida `tamanho_lote >= 1`; abaixo disso responde `400` com `{"message": "O tamanho do lote deve ser pelo menos 1."}`.
3. Chama `parar_vision_workers()`, que para todos os processos de visão e limpa o registro global `workers`.
4. Chama `iniciar_vision_workers(tamanho_lote=tamanho_lote)` para recriar os workers com o novo tamanho de lote.

O valor vem **da URL**, não do corpo — o docstring da função menciona um JSON `{"tamanho_lote": 2}`, mas nenhum corpo é lido.

⚠️ **Estado atual**: o passo 4 está quebrado. `iniciar_vision_workers` declara `cameras_id` como parâmetro posicional obrigatório e a rota o omite, então a chamada levanta `TypeError` e a requisição termina em `500`. Como o passo 3 já executou, o efeito prático da rota hoje é **parar toda a visão computacional sem reiniciá-la**; é necessário reiniciar o processo do backend para recuperar os workers.

## Active Learning — `POST /active-learning/toggle`

- Permissão: **admin ou supervisor** (`@perfil_required('admin', 'supervisor')`).
- Corpo JSON: `{"enabled": true}` ou `{"enabled": false}`. Se o corpo estiver vazio ou sem a chave, o padrão é `true`.
- Efeito: escreve `1` (ativado) ou `0` (desativado) no arquivo `assets/modelo/active_learning/active_learning.flag`. O arquivo nunca é removido — desativar apenas grava `0`.
- Resposta `200`: `{"message": "Active Learning ativado com sucesso.", "enabled": true}`.
- Não existe rota `GET` de status; o estado só pode ser lido diretamente no arquivo de flag.

Com a flag em `1`, o worker executa, por frame, a amostragem por incerteza em `_processar_active_learning`:

1. Lê o arquivo de flag; se ausente ou diferente de `1`, não faz nada.
2. Só considera o frame se houver ao menos uma detecção com confiança entre `0.3` e `0.7`.
3. Respeita um cooldown de 5 s (em memória, por processo de worker e compartilhado por todas as câmeras do lote).
4. Salva, em thread separada, o frame limpo em `assets/modelo/active_learning/dataset_captura/images/frame_al_<timestamp_ms>.jpg` e as anotações em `.../labels/frame_al_<timestamp_ms>.txt`, no formato `classe x_centro y_centro largura altura : confiança`.

## Curadoria

`GET /curadoria` serve `templates/curadoria.html`, a interface de revisão do dataset capturado. As rotas de apoio (prefixo `/api`) operam sobre os diretórios `source_dir` (capturas) e `target_dir` (dataset tratado) resolvidos por `CuradoriaService`:

- `GET /api/config` — devolve `source_dir` e `target_dir` em uso.
- `POST /api/config` — **admin**; corpo com `source_dir` e `target_dir` obrigatórios (strings não vazias) e `classes` opcional (lista de strings). Atualiza a configuração em memória, cria os diretórios de destino e grava um arquivo YAML.
- `GET /api/classes` — lista `{id, name}` das classes carregadas de `assets/config.yaml`.
- `GET /api/samples/count` — total de imagens em `source_dir/images` que possuem o `.txt` correspondente em `source_dir/labels`.
- `GET /api/samples?start=&end=` — página de amostras (`start` padrão `0`, `end` padrão `100`), cada uma com `id`, `image_file` e `label_file`. Intervalo inválido devolve lista vazia.
- `GET /api/image/<filename>` — serve a imagem de captura (`404` se não existir).
- `GET /api/labels/<filename>` — devolve as caixas do arquivo de label como `{box_id, class_id, class_name, x_center, y_center, width, height, confidence, valid}`, aceitando o sufixo `: confiança` gravado pelo Active Learning.
- `POST /api/save-and-move` — corpo `{id, image_file, label_file, boxes, apply_augmentation, allow_validation_split, split}`. Regrava o label apenas com as caixas marcadas `valid` (coordenadas fixadas em `[0,1]`), move a imagem para `train/` ou `val/` do `target_dir` e remove o label de origem. O destino é `split` quando informado (`train`/`val`); com `allow_validation_split` e sem `split`, usa ~20% para validação, mantendo no mesmo destino imagens cujos timestamps estão a menos de 60 s de distância. Com `apply_augmentation` e destino `train`, gera cópias aumentadas via `AugmentationService`. Resposta: `{"status": "sucesso", "split": "train|val"}`.
- `DELETE /api/sample/<base_name>` — remove a imagem (`.jpg`/`.jpeg`/`.png`) e o label de origem. Resposta: `{"status": "removido"}`.

Não há, no backend, rota de treinamento ou de publicação de novo modelo: a curadoria apenas prepara o dataset em disco.

## Socket.IO

O Socket.IO é inicializado em `app.py` com `async_mode='threading'`, `message_queue=REDIS_URL` (para que os processos de visão também consigam emitir) e `cors_allowed_origins="*"`.

Eventos realmente implementados:

| Evento | Direção | Descrição |
| --- | --- | --- |
| `connect` | cliente → servidor | Handler em `events/alertas_events.py`. Recusa a conexão (`return False`) se não houver `user_id` na sessão ou se a consulta de setores falhar. Caso contrário, inscreve o socket nas salas `setor_<id>` dos setores de que o usuário é responsável. |
| `disconnect` | cliente → servidor | Apenas registra log no servidor. |
| `novo_alerta` | servidor → cliente | Único evento emitido pelo backend. Payload: `id_monitorar`, `id_camera`, `id_zona`, `id_usuario`, `nome_zona`, `nome_camera`, `nome_setor`, `evento`, `severidade`, `tipo_deteccao`. |

Roteamento de `novo_alerta`, conforme `services/alertas_service.py`:

- **severidade 3** → `emitir_evento_global`, ou seja, **broadcast para todos os clientes conectados**, sem filtro de setor;
- **outras severidades** → `emitir_evento_setor`, direcionado à sala `setor_<id>` do setor da zona ou da câmera. Se o setor não for resolvido, nenhum evento é emitido.

Observações sobre o que o código **não** garante: a inscrição em salas é feita apenas no `connect`, então mudanças de responsabilidade por setor só passam a valer numa nova conexão; as salas não são revalidadas por emissão; e o `cors_allowed_origins="*"` do Socket.IO não acompanha a variável `DEV_INSECURE`, valendo em qualquer ambiente. Trate o roteamento por sala como organização de tráfego, não como controle de acesso.

## Integração com o alarme ESP32

Comandos são publicados via MQTT no tópico `alarme/<endereco_esp32>/comando`: `DISPARAR` quando um alerta de EPI com alarme associado é registrado e `RESET` quando o alerta é marcado como resolvido. O endereço vem da tabela `alarmes`, ligada ao registro de `monitorar` da zona. Detalhes do dispositivo físico: [Alarme ESP32 MQTT](https://github.com/iurycar/alarme-esp32).

## Integração com o frontend

Suba, nesta ordem: PostgreSQL, Redis, o worker RQ da fila `emails` (opcional) e o backend (`python app.py`). Em seguida sirva o frontend em outra porta (ex.: `http://localhost:8080`). O frontend deve enviar `credentials: 'include'` em todas as requisições e conectar ao Socket.IO na mesma origem do backend. Para desenvolvimento local com origens distintas, mantenha `DEV_INSECURE=true` — caso contrário os cookies exigem HTTPS e o CORS não libera a origem do frontend.

## Limitações técnicas conhecidas

Itens abaixo foram confirmados no código desta revisão do backend.

**Rotas com falha em tempo de execução**

- `POST /video/lote/<tamanho_lote>` — para todos os workers e falha ao reiniciá-los (`iniciar_vision_workers` chamado sem `cameras_id`, que é obrigatório): retorna `500` e deixa a visão computacional parada até o backend ser reiniciado. (`controller/visao_routes.py`, `worker/vision_manager.py`)
- `DELETE /zonas/<id>` — `ZonasService.deletar_zona` chama `self.zonas_repository.obter_zona_por_id`, método que não existe no repositório (o nome correto é `get_zona_por_id`): a exceção não é tratada e a rota responde `500`. (`services/zonas_service.py`)
- `GET /users` e `GET /users/ativos` — a serialização usa `usuario.is_admin` e `usuario.is_ativo` sem chamar os métodos, então o `jsonify` recebe objetos de método e falha; o `except` genérico da rota converte isso em `500`. (`services/usuario_service.py`)
- `POST /api/config` — `ConfigDTO.from_dict` só atribui a variável `classes` dentro do `if 'classes' in data`, mas a usa sempre no retorno: um corpo sem `classes` provoca `UnboundLocalError` e `500`. (`schemas/config_dto.py`)

**Divergências entre contrato e persistência**

- `POST /cameras/registrar` aceita `rotacao`, `espelhar_horizontal` e `espelhar_vertical` no DTO, mas o `INSERT` do repositório não grava esses campos: a câmera nasce sempre com os padrões do banco (`0`, `false`, `false`). Use `PUT /cameras/<id>` para definir as transformações. (`repository/cameras_repository.py`)
- `PUT /users/<id>` grava o campo `senha` **exatamente como recebido**, sem passar pelo bcrypt, e força `acesso = NULL`. Atualizar um usuário por essa rota invalida o login dele e apaga o último acesso. O `usuario_id` da URL também é ignorado — o registro alterado é o do `id` presente no corpo. (`services/usuario_service.py`, `repository/usuario_repository.py`)
- `UsuarioService.obter_status_ativo` retorna o método `is_ativo` em vez do valor booleano; como o método é sempre "verdadeiro", `GET /session` não bloqueia usuário desativado. O bloqueio por inatividade em `login_required`/`perfil_required` depende de `session['user_ativo']`, definido apenas no login.
- `CuradoriaService.atualizar_configuracao` grava o YAML em `config.yaml` relativo ao diretório de trabalho do processo, não em `assets/config.yaml`, que é o arquivo lido na inicialização: a alteração não sobrevive a um restart.
- Zonas com vários EPIs: o worker agrega todas as categorias em `epis_categoria`, mas mantém apenas o primeiro `id_monitorar` da zona. Os alertas de EPI dessa zona ficam todos vinculados a esse primeiro registro de `monitorar`, e é ele que determina qual alarme é disparado. (`repository/monitoramento_repository.py`)

**Operação e ambiente**

- `assets/tabelas_spi-postgres.sql` tem erro de sintaxe na tabela `zonas` (vírgula ausente antes de `CONSTRAINT chk_zonas_limites`) e o `DROP TABLE` inicial não inclui `estatisticas`.
- `app.py` sobe com `debug=True` fixo no código. Não use como está em produção.
- O modelo de pose `yolov8m-pose.pt` é exigido por `_ensure_models_loaded()` mas não é versionado; sem ele os workers falham ao carregar os modelos.
- Os e-mails de alerta crítico são apenas **enfileirados** na fila RQ `emails`. Sem um `rq worker emails` em execução, nenhum e-mail é enviado.
- Cada `Connection()` abre uma conexão `psycopg2` dedicada, sem pool; e `aplicar_transformacoes_frame` consulta a câmera no banco **a cada frame capturado**, o que gera um `SELECT` por frame por câmera.
- `GET /video/<id>` mantém um gerador em laço infinito por requisição; não há limite de clientes simultâneos por câmera nem encerramento explícito quando o worker é parado.
- Só é possível mudar o tamanho de lote dos workers pela rota quebrada acima; o valor inicial (`6`) está fixo em `app.py`.
