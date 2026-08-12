-- 1. POPULAR TABELA USUARIOS
INSERT INTO usuarios (nome, sobrenome, email, senha, perfil, admin_, unidade, telefone, ativo) VALUES
('Carlos', 'Silva', 'admin@visaoepi.com', '$2b$12$tjVGNW/9WdVEriWWi8H5JeMk65wr3Se62V3AOx.CTyQgVann2RmE.', 'Administrador', TRUE, 'Unidade SP', '(11) 98765-4321', TRUE),
('Ana', 'Souza', 'ana@visaoepi.com', '$2b$12$tjVGNW/9WdVEriWWi8H5JeMk65wr3Se62V3AOx.CTyQgVann2RmE.', 'Operador', FALSE, 'Unidade SP', '(11) 91234-5678', TRUE),
('Roberto', 'Lima', 'roberto@visaoepi.com', '$2b$12$tjVGNW/9WdVEriWWi8H5JeMk65wr3Se62V3AOx.CTyQgVann2RmE.', 'Supervisor', FALSE, 'Unidade RJ', '(21) 99999-8888', TRUE);

-- 2. POPULAR TABELA SETORES
INSERT INTO setores (nome) VALUES
('Linha de Montagem A'),
('Almoxarifado Central'),
('Área de Solda');

-- 3. POPULAR TABELA CAMERAS (Depende de setores)
-- Câmera 1 e 2 no Setor 1, Câmera 3 no Setor 3
INSERT INTO cameras (ip, id_setor) VALUES
('192.168.1.101', 1),
('192.168.1.102', 1),
('192.168.2.201', 3);

-- 4. POPULAR TABELA ZONAS (Depende de cameras)
-- Coordenadas simuladas (x1, y1, x2, y2)
INSERT INTO zonas (nome, x1, y1, x2, y2, id_camera) VALUES
('Entrada Principal', 10, 10, 100, 200, 1),
('Posto de Montagem 01', 120, 50, 300, 250, 1),
('Célula de Solda 01', 50, 50, 400, 400, 3);

-- 5. POPULAR TABELA EPIS
INSERT INTO epis (nome, categoria, certificado, validade, estoque, quantidade_min, em_uso) VALUES
('Capacete de Segurança H-700', 'Capacete', 'CA-12345', '2027-12-31', 50, 10, 5),
('Óculos de Proteção Incolor', 'Óculos', 'CA-67890', '2026-10-15', 120, 20, 15),
('Máscara de Solda Automática', 'Máscara', 'CA-11223', '2028-05-20', 15, 5, 3);

-- 6. POPULAR TABELA MONITORAR (Depende de zonas, cameras e epis)
-- Regras de monitoramento ativas no sistema
INSERT INTO monitorar (id_zona, id_camera, id_epi) VALUES
(1, 1, 1), -- Monitorar Capacete na Entrada Principal (Câmera 1)
(2, 1, 2), -- Monitorar Óculos no Posto de Montagem 01 (Câmera 1)
(3, 3, 3); -- Monitorar Máscara de Solda na Célula de Solda 01 (Câmera 3)

-- 7. POPULAR TABELA ALERTAS (Depende de monitorar e usuarios)
-- Alertas gerados pelo sistema por falta de EPI
INSERT INTO alertas (resolvido, data_hora, id_monitorar, id_usuario) VALUES
(TRUE,  CURRENT_TIMESTAMP - INTERVAL '2 hours', 1, 1), -- Alerta resolvido pelo usuário Carlos
(FALSE, CURRENT_TIMESTAMP - INTERVAL '30 minutes', 2, 1), -- Alerta pendente
(FALSE, CURRENT_TIMESTAMP - INTERVAL '5 minutes', 3, 2);  -- Alerta recente atribuído à Ana

SELECT * FROM usuarios;
