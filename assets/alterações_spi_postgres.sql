ALTER TABLE zonas DROP CONSTRAINT IF EXISTS chk_zonas_limites;
ALTER TABLE zonas DROP COLUMN x;
ALTER TABLE zonas DROP COLUMN y;
ALTER TABLE zonas DROP COLUMN largura;
ALTER TABLE zonas DROP COLUMN altura;

-- Adiciona a coluna poligono
ALTER TABLE zonas ADD COLUMN poligono JSONB NOT NULL DEFAULT '[]'::jsonb;