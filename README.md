# SPI — Backend

Projeto elaborado para o Challenge FIAP 2026 com parceria da SPI. Descritivo do backend responsável pela autenticação de usuários, inventário de EPIs, gerenciamento de alertas, monitoramento de câmeras, setores e zonas, integração com alarmes físicos (ESP32 via MQTT) e visão computacional em tempo real usando YOLO e OpenCV em uma arquitetura por camadas.

## Funcionamento do sistema

O backend é estruturado em uma arquitetura em camadas (Controller, Service, Repository, Model/Schema) com suporte a processamento concorrente de visão computacional e mensageria.

1. Camada de API (Controller e Blueprints): Recebe requisições HTTP REST, gerencia autenticação baseada em sessão persistida no Redis e expõe endpoints para gerenciamento de todas as entidades.
2. Camada de Negócio (Services): Aplica as regras da aplicação, valida operações, controla a integridade dos dados e gerencia os eventos do sistema.
3. Camada de Persistência (Repository e Connection): Gerencia conexões nativas com o PostgreSQL e executa queries SQL para persistência de dados.
4. Processamento de Visão Computacional (Workers): Ao iniciar a aplicação (`app.py`), o `VisionManager` cria um processo independente (`multiprocessing.Process`) para cada câmera cadastrada. O `VisionWorker` captura o stream da câmera (webcam, arquivo ou RTSP), executa a inferência do modelo YOLO para identificação de pessoas e EPIs, e verifica se as detecções violam as regras de zonas delimitadas.
5. Emissão de Alertas e Notificações: Quando uma infração é identificada, o sistema valida no Redis se o alerta é recente para evitar duplicação. Em caso de novo alerta, o registro é salvo no PostgreSQL, um evento WebSocket é emitido via SocketIO para atualização instantânea do frontend e, se necessário, é enviado um e-mail de alerta crítico ou um comando MQTT para o alarme físico ESP32.
6. Integração com Alarme ESP32: Comandos de disparo ou desligamento são publicados via MQTT em tópicos dedicados (`alarme/<endereco_esp32>/comando`), permitindo que a resolução de alertas pela API desative o alarme físico remotamente.

## Arquitetura de diretórios

- `app.py`: inicialização da aplicação Flask, configuração de sessão no Redis, CORS, WebSockets e inicialização dos workers de visão.
- `assets/`: scripts SQL para criação e população do banco PostgreSQL, diagramas de dados e arquivos da visão computacional.
- `connection/`: gerenciamento da conexão com o banco de dados PostgreSQL.
- `controller/`: definição das rotas HTTP (Blueprints) agrupadas por entidade.
- `core/`: validações de segurança e tratamento de exceções personalizadas.
- `events/`: manipuladores e registro de eventos em tempo real via WebSocket.
- `models/`: representação das entidades do sistema.
- `repository/`: camada de acesso ao banco de dados e execução de queries SQL.
- `schemas/`: DTOs (Data Transfer Objects) para estruturação de entrada e saída de dados.
- `services/`: regras de negócio, gerenciamento dos modelos de visão e envio de notificações.
- `tasks/`: tarefas em segundo plano para envio de e-mails de alerta e publicação MQTT para o alarme.
- `worker/`: gerenciador (`VisionManager`) e processos individuais (`VisionWorker`) para processamento das câmeras.

## Requisitos

- Python 3.10 ou superior.
- PostgreSQL 12 ou superior.
- Redis Server.
- Mosquitto MQTT Broker (caso utilize integração com alarme físico ESP32).
- Dependências descritas no arquivo `requirements.txt`.

## Configuração local

1. Crie e ative o ambiente virtual Python:

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

2. Instale as dependências do projeto:

```bash
pip install -r requirements.txt
```

3. Configure o banco de dados PostgreSQL:
   - Crie o banco de dados PostgreSQL (exemplo: `spi_database`).
   - Execute o script de criação de tabelas em `assets/tabelas_spi-postgres.sql`.
   - Opcionalmente, execute o script de inserções iniciais em `assets/inserções_spi-postgres.sql`.

4. Configure as variáveis de ambiente:
   - Copie o arquivo `exemple.env` para `.env`:

```bash
cp exemple.env .env
```

   - Ajuste os valores no arquivo `.env` de acordo com seu ambiente:
     - `SECRET_KEY`: chave secreta para assinatura das sessões Flask.
     - `DEV_INSECURE`: defina como `true` para ambiente de desenvolvimento local (libera CORS e ajusta cookies de sessão).
     - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`, `DB_PASSWORD`: credenciais do banco PostgreSQL.
     - `REDIS_URL`: URL de conexão do Redis (exemplo: `redis://localhost:6379/0`).
     - `BROKER_ADDRESS`, `BROKER_PORT`: endereço e porta do broker MQTT.
     - `EMAIL_ADDRESS`, `EMAIL_PASSWORD`: credenciais de e-mail para envio de alertas críticos.

   - Gerar chave secreta aleatória (opcional):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Execução

1. Certifique-se de que os serviços do PostgreSQL e do Redis estejam em execução.
2. Inicie o servidor backend:

```bash
python app.py
```

Por padrão, o servidor Flask será executado em `http://127.0.0.1:5000` ou no IP configurado. Ao ser iniciado, o servidor criará automaticamente os workers de visão computacional para todas as câmeras ativas cadastradas no banco de dados.

## Endpoints principais

### Autenticação

- `POST /login`: autentica o usuário e inicia a sessão no Redis.
- `GET /session`: valida e retorna os dados da sessão atual.
- `POST /logout`: encerra a sessão do usuário.
- `POST /signup`: cadastra um novo usuário.

### EPIs

- `GET /epis` e `GET /epis/<id>`: lista todos os EPIs ou busca por ID.
- `POST /epis`: cadastra um novo EPI.
- `PUT /epis/<id>`: atualiza um EPI existente.
- `DELETE /epis/<id>`: remove um EPI.

### Alertas e Estatísticas

- `GET /alertas`: consulta geral de alertas.
- `GET /alertas/<id>`: busca alerta específico por ID.
- `GET /alertas/camera/<camera_id>`: consulta alertas por câmera.
- `GET /alertas/zona/<zona_id>`: consulta alertas por zona.
- `GET /alertas/estatisticas/epi`: estatísticas de alertas agrupadas por tipo de EPI.
- `GET /alertas/estatisticas/periodo`: estatísticas de alertas por período (parâmetro `periodo`).
- `PUT /alertas/<id>/resolvido`: marca um alerta como resolvido (desativa alarme físico se aplicável).
- `DELETE /alertas/<id>`: deleta um registro de alerta.

### Câmeras, Setores e Zonas

- `GET /cameras`, `POST /cameras/registrar`, `PUT /cameras/<id>`, `DELETE /cameras/<id>`
- `GET /cameras/status`: retorna o status em tempo real de cada câmera (`Ativo`, `Inativo`, `Desconectado`).
- `GET /cameras/<id>/zonas`: lista zonas associadas a uma câmera.
- `GET /setores`, `POST /setores/registrar`, `PUT /setores/<id>`, `DELETE /setores/<id>`
- `GET /zonas`, `POST /zonas/registrar`, `PUT /zonas/<id>`, `DELETE /zonas/<id>` (notifica automaticamente o worker da câmera para recarregar as zonas).

### Visão Computacional

- `GET /video`, `GET /video/<camera_id>`: stream de vídeo MJPEG da câmera especificada.
- `GET /detections/<camera_id>`: últimas detecções, contagem de classes e status de conexão da câmera.
- `POST /active-learning/toggle`: ativa ou desativa a captura de frames para Active Learning.

## Integração com o alarme ESP32

O sistema integra-se com alarmes baseados em ESP32 via protocolo MQTT. Mais detalhes sobre a construção e configuração do dispositivo físico encontram-se no repositório: [Alarme ESP32 MQTT](https://github.com/iurycar/alarme-esp32).

## Integração com o frontend

Inicie primeiro o PostgreSQL, Redis e o backend Python. Em seguida, sirva o frontend HTTP em outra porta (por exemplo, `http://localhost:8080`). O frontend centraliza as chamadas em `js/api.js`, enviando credenciais de sessão em todas as requisições (`credentials: include`) e escutando eventos em tempo real via WebSocket (`Flask-SocketIO`).

## Observações

- Nunca inclua credenciais reais em commits ou documentação pública.
- Certifique-se de que o Redis esteja rodando antes de iniciar o backend, pois as sessões e mensageria dependem dele.
- Sem o banco PostgreSQL configurado e alimentado, as rotas da API não poderão ser validadas integralmente.
- O carregamento dos modelos YOLO pode exigir memória RAM/VRAM adicional e aumentar o tempo de inicialização inicial dos workers.
