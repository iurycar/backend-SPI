-- Executar UMA VEZ, sobre o schema selecionado pela conexão.
-- A transação é controlada pelo chamador (psql --single-transaction
-- --set=ON_ERROR_STOP=1 ou connection.commit/rollback no Python).
-- Parar API/workers antes de aplicar e reiniciar com o código atualizado.
-- Não usar o DDL de instalação, que contém DROP TABLE, como migração.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

LOCK TABLE alertas IN ACCESS EXCLUSIVE MODE;

-- Somente o histórico recebe legado; novos INSERTs têm default epi.
ALTER TABLE alertas
    ADD COLUMN tipo_deteccao VARCHAR(20) NOT NULL DEFAULT 'legado',
    ADD COLUMN id_camera INTEGER REFERENCES cameras(id_camera) ON DELETE RESTRICT,
    ALTER COLUMN id_monitorar DROP NOT NULL;

ALTER TABLE alertas
    ALTER COLUMN tipo_deteccao SET DEFAULT 'epi',
    ADD CONSTRAINT chk_alertas_tipo_deteccao CHECK (
        tipo_deteccao IN ('epi', 'postura_tronco', 'postura_rotacao', 'queda', 'legado')
    ),
    ADD CONSTRAINT chk_alertas_vinculo CHECK (
        (tipo_deteccao IN ('epi', 'legado') AND id_monitorar IS NOT NULL AND id_camera IS NULL)
        OR
        (tipo_deteccao IN ('postura_tronco', 'postura_rotacao', 'queda')
         AND id_monitorar IS NULL AND id_camera IS NOT NULL)
    );
