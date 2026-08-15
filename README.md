# BACKEND SPI - 2026

## Arquitetura em camadas

* **app.py**:
* **assets/**: Recursos para funcionamento do sistema
* **connection/**: Pacote responsável por criar a conexão com PostgreSQL
* **controller/**: Pacote responsável por estabelecer os ENDPOINTS da requisições HTTP
* **core/**: Pacote responsável por realizar verificações de segurança
* **models/**: Pacote responsável por definir os classes/objetos  
* **repository/**: Pacote responsável por realizar as query (ex. SELECT) nos banco de dados
* **schemas/**: Pacote responsável por criar os Data Transfer Object (DTO)
* **services/**: Pacote responsável por realizar as operações do sistema

```
Backend-SPI-2026/
├── assets/
│    ├── modelo/
│    │    ├── treinamento/
│    │    │    ├── weights/
│    │    │    │    ├── best.pt
│    │    │    │    └── last.pt
│    │    │    └── args.yaml
│    │    ├── data.yaml
│    │    └── index.html
│    ├── inserções_spi-postgres.sql
│    ├── modelo_DB.mwb
│    ├── modelo_DB.mwb.bak
│    └── tabelas_spi-postgres.sql
├── connection/
│    ├── __init__.py
│    └── conn.py
├── controller/
│    ├── __init__.py
│    ├── epi_routes.py
│    ├── ...
│    └── zonas_routes.py
├── core/
│    ├── __init__.py
│    ├── errors.py
│    ├── security.py
│    └── validators.py
├── models/
│    ├── __init__.py
│    ├── ...
│    └── zonas.py
├── repository/
│    ├── __init__.py
│    ├── epi_repository.py
│    ├── ...
│    └── zonas_repository.py
├── schemas/
│    ├── __init__.py
│    └── usuario_dto.py
├── services/
│    ├── __init__.py
│    ├── epi_service.py
│    ├── ...
│    └── zonas_service.py
├── __init__.py
├── .env
├── app.py
└── requirements.txt

```

## ENDPOINTS

O servidor estará disponível em `http://127.0.0.1:5000` e pronto para receber requisições.

### Usuário

- `POST /login` - Recebe os dados de login da sessão
- `POST /logout` - Remove os dados da sessão
- `POST /signup` - Cadastra um novo usuário

### EPIs

- `GET /epis` - Lista as EPIs

### Visão Computacional

- `/video` - Acessa o vídeo da visão
- `/detections` - Retorna a lista de detecções

### Zonas
- `GET /zonas` - Lista todas as zonas
- `GET /zonas/<int:zona_id>` - Obtém a zona por ID
- `GET /zonas/camera/<int:camera_id>` - Lista as zonas por ID da câmera