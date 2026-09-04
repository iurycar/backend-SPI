# SPI — Backend

API do Sistema de Proteção Individual (SPI), responsável por autenticação, inventário de EPIs, alertas, câmeras, setores, zonas e visão computacional. O projeto usa Python, Flask e PostgreSQL em uma arquitetura por camadas.

## Arquitetura

- `app.py`: configuração do Flask, sessão, CORS e registro dos blueprints.
- `connection/`: conexão com PostgreSQL.
- `controller/`: rotas HTTP.
- `services/`: regras de aplicação e serialização.
- `repository/`: consultas e persistência.
- `events/`: registro de eventos com WebSocket.
- `models/` e `schemas/`: entidades e DTOs.
- `core/`: segurança e tratamento de erros.
- `assets/`: scripts SQL e recursos da visão computacional.

## Requisitos

- Python 3.10 ou superior.
- PostgreSQL com o schema de `assets/tabelas_spi-postgres.sql`.
- Dependências de `requirements.txt`.

## Configuração local

```bash
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
```

Copie `exemple.env` para `.env` e preencha os valores locais. `.env` é ignorado pelo Git e não deve ser publicado.

```bash
cp exemple.env .env
```

Variáveis usadas: `SECRET_KEY`, `DEV_INSECURE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME` e `DB_PASSWORD`.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Execução

```bash
python app.py
```

Por padrão, o Flask atende em `http://127.0.0.1:5000`. O frontend deve ser servido por HTTP. Requisições autenticadas usam cookie de sessão e `credentials: include`.

Em desenvolvimento (`DEV_INSECURE=true`), o CORS aceita origens locais com credenciais. Em produção, configure HTTPS, cookies seguros e origens explícitas.

## Endpoints principais

### Autenticação

- `POST /login`: inicia a sessão e retorna o usuário.
- `GET /session`: valida a sessão atual.
- `POST /logout`: encerra a sessão.
- `POST /signup`: cadastra usuário.

### EPIs

- `GET /epis` e `GET /epis/<id>`
- `POST /epis`
- `PUT /epis/<id>`
- `DELETE /epis/<id>`

### Alertas

- consulta geral, individual, por câmera e por zona
- `PUT /alertas/<id>/resolvido`
- `DELETE /alertas/<id>`

### Câmeras, setores e zonas

- consulta, cadastro, atualização e exclusão
- associação entre câmeras, setores e zonas

### Visão computacional

- `GET /video` e `GET /video/<camera_id>`: stream MJPEG.
- `GET /detections`: detecções recentes.
- `POST /active-learning/toggle`: ativa ou desativa a captura de Active Learning.

## Integração com o frontend

Inicie primeiro PostgreSQL e backend. Depois sirva o frontend em outra porta, por exemplo `http://localhost:8080`. O frontend centraliza chamadas em `js/api.js`, envia cookies e trata sessões expiradas.

## Observações

- Nunca inclua credenciais reais em commits ou documentação.
- Sem PostgreSQL configurado, não é possível validar integralmente as rotas.
- Pesos já versionados podem exigir memória e aumentar o tempo de inicialização.
