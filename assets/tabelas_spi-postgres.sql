DROP TABLE IF EXISTS alertas          CASCADE;
DROP TABLE IF EXISTS alarmes          CASCADE;
DROP TABLE IF EXISTS monitorar        CASCADE;
DROP TABLE IF EXISTS epis             CASCADE;
DROP TABLE IF EXISTS zonas            CASCADE;
DROP TABLE IF EXISTS cameras          CASCADE;
DROP TABLE IF EXISTS responsabilidade CASCADE;
DROP TABLE IF EXISTS setores          CASCADE;
DROP TABLE IF EXISTS usuarios         CASCADE;


-- ========================================================
-- TABELA: usuarios
-- ========================================================
CREATE TABLE usuarios (
    id_usuario      INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome            VARCHAR(40)  NOT NULL,
    sobrenome       VARCHAR(90)  NOT NULL,
    email           VARCHAR(60)  NOT NULL UNIQUE,
    senha           VARCHAR(255) NOT NULL,
    perfil          VARCHAR(20)  NOT NULL,
    unidade         VARCHAR(45),
    telefone        VARCHAR(45),
    ativo           BOOLEAN      NOT NULL DEFAULT TRUE,
    acesso          TIMESTAMP
);


-- ========================================================
-- TABELA: setores
-- ========================================================
CREATE TABLE setores (
    id_setor        INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome            VARCHAR(45)  NOT NULL
);


-- ========================================================
-- TABELA: responsabilidade (N:N entre usuarios e setores)
-- ========================================================
CREATE TABLE responsabilidade (
    id_responsabilidade INTEGER  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario          INTEGER  NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    id_setor            INTEGER  NOT NULL REFERENCES setores(id_setor)   ON DELETE CASCADE,
    CONSTRAINT uq_usuario_setor  UNIQUE (id_usuario, id_setor)
);


-- ========================================================
-- TABELA: cameras
-- ========================================================
CREATE TABLE cameras (
    id_camera       INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome            VARCHAR(45),
    ip              VARCHAR(255) UNIQUE,
    id_setor        INTEGER      NOT NULL REFERENCES setores(id_setor) ON DELETE CASCADE
);


-- ========================================================
-- TABELA: zonas
-- ========================================================
CREATE TABLE zonas (
    id_zona         INTEGER      	GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome            VARCHAR(40)  	NOT NULL DEFAULT 'Nome não definido',
    x               NUMERIC(6, 5)   NOT NULL,
    y               NUMERIC(6, 5)   NOT NULL,
    largura         NUMERIC(6, 5)   NOT NULL,
    altura          NUMERIC(6, 5)   NOT NULL,
    permitido       BOOLEAN      	NOT NULL DEFAULT TRUE,
    id_camera       INTEGER      	NOT NULL REFERENCES cameras(id_camera) ON DELETE CASCADE

	-- Garante valores normalizados entre 0 e 1
	CONSTRAINT chk_zonas_limites CHECK (
        x >= 0.0 AND x <= 1.0 AND
        y >= 0.0 AND y <= 1.0 AND
        largura > 0.0 AND largura <= 1.0 AND
        altura > 0.0 AND altura <= 1.0 AND
        (x + largura) <= 1.0 AND
        (y + altura) <= 1.0
    )
);


-- ========================================================
-- TABELA: epis
-- ========================================================
CREATE TABLE epis (
    id_epi          INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome            VARCHAR(45)  NOT NULL,
    categoria       VARCHAR(45)  NOT NULL,
    certificado     VARCHAR(45)  NOT NULL,
    validade        DATE         NOT NULL,
    estoque         INTEGER      NOT NULL DEFAULT 0,
    quantidade_min  INTEGER      NOT NULL DEFAULT 0,
    em_uso          INTEGER      NOT NULL DEFAULT 0
);


-- ========================================================
-- TABELA: monitorar
-- ========================================================
CREATE TABLE monitorar (
    id_monitorar    INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_zona         INTEGER      NOT NULL REFERENCES zonas(id_zona) ON DELETE CASCADE,
    id_epi          INTEGER      REFERENCES epis(id_epi)            ON DELETE SET NULL
);


-- ========================================================
-- TABELA: alarmes
-- ========================================================
CREATE TABLE alarmes (
    id_alarme       INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    endereco        VARCHAR(255) NOT NULL,
    id_monitorar    INTEGER      NOT NULL REFERENCES monitorar(id_monitorar) ON DELETE CASCADE
);


-- ========================================================
-- TABELA: alertas (Ocorrências registradas pelo sistema)
-- ========================================================
CREATE TABLE alertas (
    id_alerta       INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resolvido       BOOLEAN      NOT NULL DEFAULT FALSE,
    data_hora       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_monitorar    INTEGER      NOT NULL REFERENCES monitorar(id_monitorar) ON DELETE RESTRICT,
    id_usuario      INTEGER      REFERENCES usuarios(id_usuario)             ON DELETE SET NULL, -- Usuário que atendeu/resolveu
    evento          VARCHAR(40)  NOT NULL DEFAULT 'Sem EPI ou zona proibida',
    severidade      INTEGER      NOT NULL DEFAULT 1
);