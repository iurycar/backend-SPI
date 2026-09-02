# BACKEND SPI - 2026

## Arquitetura em camadas

* **app.py**:
* **assets/**: Recursos para funcionamento do sistema
* **assets/modelo/active_learning**: Armazena o dataset bruto e tratado do Active Learning
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
│    │    ├── active_learnig/
│    │    │    ├── dataset_captura
│    │    │    │    ├── images
│    │    │    │    └── labels
│    │    │    └── dataset_tratado
│    │    │         ├── images
│    │    │         └── labels
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
- `GET /epis/<int:epi_id>` - Busca a EPI por ID
- `POST /epis` - Registra uma nova EPI
- `PUT /epis/<int:epi_id>` - Atualiza uma EPI por ID
- `DELETE /epis/<int:epi_id>` - Deleta uma EPI por ID

### Visão Computacional

- `GET /video` - Acessa o vídeo da visão
- `GET /video/<int:camera_id>` - Acessa o vídeo da câmera especificada
- `GET /detections` - Retorna a lista de detecções
- `POST /active-learning/toggle` - Ativa e desativa o método de Active Learning

### Zonas
- `GET /zonas` - Lista todas as zonas
- `GET /zonas/<int:zona_id>` - Obtém a zona por ID
- `POST /zonas/registrar` - Registra uma nova zona 
- `PUT /zonas/<int:zona_id>` - Atualiza uma zona por ID
- `DELETE /zonas/<int:zona_id>` - Deleta uma zona por ID

### Câmeras
- `GET /cameras` - Lista todas as câmeras
- `GET /cameras/<int:camera_id>` - Obtém a câmera por ID
- `GET /cameras/setor/<int:setor_id>` - Lista câmeras por ID do setor
- `GET /cameras/<int:camera_id>/zonas` - Lista zonas associadas à câmera
- `POST /cameras/registrar` - Registra uma nova câmera
- `PUT /cameras/<int:camera_id>` - Atualiza câmera por ID
- `DELETE /cameras/<int:camera_id>` - Deleta uma câmera por ID

### Alertas
- `GET /alertas` - Lista todos os alertas
- `GET /alertas/<int:alerta_id>` - Obtém alerta por ID
- `GET /alertas/camera/<int:camera_id>` - Lista alertas por ID da câmera
- `GET /alertas/zona/<int:zona_id>` - Lista alertas por ID da zona
- `PUT /alertas/<int:alerta_id>/resolvido` - Marca alerta como resolvido
- `DELETE /alertas/<int:alerta_id>` - Deleta um alerta por ID

### Setores
- `GET /setores` - Lista todos os setores
- `GET /setores/<int:setor_id>` - Obtém setor por ID
- `GET /setores/responsavel/<int:usuario_id>` - Lista setores por responsável (usuário)
- `POST /setores/registrar` - Registra um novo setor
- `PUT /setores/<int:setor_id>` - Atualiza setor por ID
- `DELETE /setores/<int:setor_id>` - Deleta setor por ID