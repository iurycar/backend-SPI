-- 1. POPULAR TABELA USUARIOS
INSERT INTO usuarios (nome, sobrenome, email, senha, perfil, unidade, telefone, ativo) VALUES
('Carlos', 'Silva', 'admin@visaoepi.com', '$2b$12$tjVGNW/9WdVEriWWi8H5JeMk65wr3Se62V3AOx.CTyQgVann2RmE.', 'Administrador', 'Unidade SP', '(11) 98765-4321', TRUE),
('Ana', 'Souza', 'ana@visaoepi.com', '$2b$12$tjVGNW/9WdVEriWWi8H5JeMk65wr3Se62V3AOx.CTyQgVann2RmE.', 'Operador', 'Unidade SP', '(11) 91234-5678', TRUE),
('Roberto', 'Lima', 'roberto@visaoepi.com', '$2b$12$tjVGNW/9WdVEriWWi8H5JeMk65wr3Se62V3AOx.CTyQgVann2RmE.', 'Supervisor', 'Unidade RJ', '(21) 99999-8888', TRUE);


-- 2. POPULAR TABELA SETORES
INSERT INTO setores (nome) VALUES
('Chão de Fábrica'),
('Tenda'),
('Sala 4'),
('SICK Visionary-B Two');


-- 3. POPULAR TABELA RESPONSABILIDADE (N:N entre usuarios e setores)
INSERT INTO responsabilidade (id_usuario, id_setor) VALUES
(1, 1), (1, 2), (1, 3), (1, 4), -- Carlos supervisiona todos os setores
(2, 1),                         -- Ana alocada no Chão de Fábrica
(3, 3),                         -- Roberto alocado na Sala 4
(3, 4);                         -- Roberto alocado na SICK Visionary-B Two


-- 4. POPULAR TABELA CAMERAS (Depende de setores)
-- Câmera 1 e 2 no Setor 1, Câmera 3 no Setor 3
INSERT INTO cameras (nome, ip, id_setor) VALUES
('Fresa 1', 'rtsp://admin:SIDI2023@10.14.22.97:554/cam/realmonitor?channel=1&subtype=0', 1),
('Fresa 2', 'rtsp://admin:SIDI2023@10.14.22.98:554/cam/realmonitor?channel=1&subtype=0', 1),
('Tenda', 'rtsp://admin:SIDI2023@10.14.22.99:554/cam/realmonitor?channel=1&subtype=0', 2),
('Sala 4', 'rtsp://admin:SIDI2023@10.14.24.6:554/cam/realmonitor?channel=1&subtype=0', 3),
('SICK Visionary-B Two', 'rtsp://10.14.22.96:554/video', 4);


-- 5. POPULAR TABELA ZONAS (Depende de cameras)
-- Coordenadas simuladas (x, y, largura, altura)
INSERT INTO zonas (nome, x, y, largura, altura, permitido, id_camera) VALUES
('Fresa 1',   				0,  0, 	1, 	1, 	TRUE,  	1), -- Zona 1 (CAM 1) (Setor 1)
('Fresa 2',   				0,  0, 	1, 	1, 	TRUE,  	1), -- Zona 2 (CAM 2) (Setor 1)
('Tenda',     				0,  0, 	1, 	1, 	TRUE,  	2), -- Zona 3 (CAM 2) (Setor 2)
('Sala 4',    				0,  0, 	1, 	1, 	TRUE,  	3), -- Zona 4 (CAM 3) (Setor 3)
('SICK Visionary-B Two',    0, 	0, 	1, 	1, 	TRUE,   4); -- Zona 5 (CAM4) (Setor 4)


-- 6. POPULAR TABELA EPIS
INSERT INTO epis (nome, categoria, certificado, validade, estoque, quantidade_min, em_uso) VALUES
('Capacete de Segurança H-700', 'Capacete', 'CA-12345', '2027-12-31', 50,  5,  6),
('Óculos de Proteção Incolor',  'Oculos',   'CA-67890', '2026-10-15', 120, 12, 4),
('Máscara de Solda Automática', 'Mascara',  'CA-11223', '2028-05-20', 30,  5, 10),
('Luva de Proteção Soldador',   'Luva',     'CA-44556', '2028-05-20', 15,  3,  8);


-- 7. POPULAR TABELA MONITORAR (Depende de zonas, cameras e epis)
-- Regras de monitoramento ativas no sistema
INSERT INTO monitorar (id_zona, id_epi) VALUES
(1, 1),    -- Regra 1: Checar Capacete na Entrada Principal
(2, 2),    -- Regra 2: Checar Óculos no Posto de Montagem 01
(3, 3),    -- Regra 3: Checar Máscara de Solda na Célula de Solda 01
(3, 4),    -- Regra 4: Checar Luva de Proteção na Célula de Solda 01
(4, NULL); -- Regra 5: Detecção de intrusão no Perímetro Restrito (sem EPI associado)


-- 8. POPULAR TABELA ALARMES
INSERT INTO alarmes (endereco, id_monitorar) VALUES
('setor_01_fresa_01', 1);


-- 9. POPULAR TABELA ALERTAS (Depende de monitorar e usuarios)
-- Alertas gerados pelo sistema por falta de EPI
INSERT INTO alertas (resolvido, data_hora, id_monitorar, id_usuario, evento, severidade) VALUES
(TRUE,  CURRENT_TIMESTAMP - INTERVAL '2 hours',    1, 1,    'Operador sem capacete detectado', 2),
(FALSE, CURRENT_TIMESTAMP - INTERVAL '30 minutes', 2, 2,    'Operador sem óculos de proteção', 1),
(FALSE, CURRENT_TIMESTAMP - INTERVAL '5 minutes',  3, NULL, 'Falta de máscara em arco elétrico ativo', 3),
(FALSE, CURRENT_TIMESTAMP - INTERVAL '1 minute',   5, NULL, 'Acesso não autorizado a zona restrita', 3);

-- TESTE DE CONSULTA PARA VERIFICAR ALERTAS GERADOS PELO SISTEMA
SELECT 
    a.id_alerta,
    a.data_hora,
    a.evento,
    a.severidade,
    a.resolvido,
    u.nome AS operador_responsavel,
    z.nome AS zona,
    c.nome AS camera,
    c.ip AS ip_camera,
    s.nome AS setor,
    e.nome AS epi_requerido
FROM alertas a
JOIN monitorar m     ON a.id_monitorar = m.id_monitorar
JOIN zonas z         ON m.id_zona = z.id_zona
JOIN cameras c       ON z.id_camera = c.id_camera
JOIN setores s       ON c.id_setor = s.id_setor
LEFT JOIN epis e     ON m.id_epi = e.id_epi
LEFT JOIN usuarios u ON a.id_usuario = u.id_usuario
ORDER BY a.data_hora DESC;