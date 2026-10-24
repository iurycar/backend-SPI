ALTER TABLE zonas DROP CONSTRAINT IF EXISTS chk_zonas_limites;
ALTER TABLE zonas DROP COLUMN x;
ALTER TABLE zonas DROP COLUMN y;
ALTER TABLE zonas DROP COLUMN largura;
ALTER TABLE zonas DROP COLUMN altura;

-- Adiciona a coluna poligono
ALTER TABLE zonas ADD COLUMN poligono JSONB NOT NULL DEFAULT '[]'::jsonb;



ALTER TABLE alertas DROP CONSTRAINT IF EXISTS chk_alertas_tipo_deteccao;
ALTER TABLE alertas DROP CONSTRAINT IF EXISTS chk_alertas_vinculo;

-- Adiciona novamente a constraint de tipos aceitando 'agachado'
ALTER TABLE alertas ADD CONSTRAINT chk_alertas_tipo_deteccao CHECK (
    tipo_deteccao IN ('epi', 'postura_tronco', 'postura_rotacao', 'queda', 'agachado', 'legado')
);

-- Adiciona novamente a constraint de vínculo incluindo 'agachado' junto às posturas da câmera
ALTER TABLE alertas ADD CONSTRAINT chk_alertas_vinculo CHECK (
    (tipo_deteccao IN ('epi', 'legado') AND id_monitorar IS NOT NULL AND id_camera IS NULL)
    OR
    (tipo_deteccao IN ('postura_tronco', 'postura_rotacao', 'queda', 'agachado')
     AND id_monitorar IS NULL AND id_camera IS NOT NULL)
);