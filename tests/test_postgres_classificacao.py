"""Real PostgreSQL, exclusively session-local temporary tables; no external notifications."""
import contextlib
import io
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import psycopg2
from dotenv import dotenv_values
from flask import Flask
from flask_socketio import SocketIO

from controller.alertas_routes import create_alertas_bp
from core.tipo_deteccao import TIPOS_POSTURA
from models.zonas import Zona
from repository.alertas_repository import AlertasRepository
from repository.setores_repository import SetoresRepository
from services.alertas_service import AlertasService
from services.visao_service import VisaoService

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / 'assets/migrations/001_classificacao_alertas.sql').read_text(encoding='utf-8')
OLD_SCHEMA = """
CREATE TEMP TABLE usuarios (id_usuario integer PRIMARY KEY, email text);
CREATE TEMP TABLE setores (id_setor integer PRIMARY KEY, nome text);
CREATE TEMP TABLE responsabilidade (
    id_usuario integer REFERENCES usuarios(id_usuario),
    id_setor integer REFERENCES setores(id_setor));
CREATE TEMP TABLE cameras (
    id_camera integer PRIMARY KEY, nome text, ip text,
    id_setor integer NOT NULL REFERENCES setores(id_setor));
CREATE TEMP TABLE zonas (
    id_zona integer PRIMARY KEY, nome text,
    id_camera integer NOT NULL REFERENCES cameras(id_camera));
CREATE TEMP TABLE epis (id_epi integer PRIMARY KEY, categoria text);
CREATE TEMP TABLE monitorar (
    id_monitorar integer PRIMARY KEY,
    id_zona integer NOT NULL REFERENCES zonas(id_zona),
    id_epi integer REFERENCES epis(id_epi));
CREATE TEMP TABLE alarmes (
    id_alarme integer PRIMARY KEY, endereco text,
    id_monitorar integer NOT NULL REFERENCES monitorar(id_monitorar));
CREATE TEMP TABLE alertas (
    id_alerta integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resolvido boolean NOT NULL DEFAULT FALSE,
    data_hora timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_monitorar integer NOT NULL REFERENCES monitorar(id_monitorar) ON DELETE RESTRICT,
    id_usuario integer REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    evento varchar(40) NOT NULL DEFAULT 'Sem EPI ou zona proibida',
    severidade integer NOT NULL DEFAULT 1);
INSERT INTO usuarios VALUES (4, 'test4@example.invalid'), (5, 'test5@example.invalid');
INSERT INTO setores VALUES (7, 'Producao');
INSERT INTO cameras VALUES (1, 'Com zona', 'test:1', 7), (2, 'Sem zonas', 'test:2', 7);
INSERT INTO responsabilidade VALUES (4, 7), (5, 7);
INSERT INTO zonas VALUES (3, 'Entrada', 1);
INSERT INTO epis VALUES (8, 'Capacete');
INSERT INTO monitorar VALUES (12, 3, 8), (13, 3, NULL);
INSERT INTO alarmes VALUES (1, 'test-device', 12);
INSERT INTO alertas (id_monitorar, id_usuario, evento, severidade, resolvido)
    VALUES (12, 4, 'queda antiga', 3, TRUE), (12, NULL, 'EPI antigo', 1, FALSE);
"""


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == '1', 'Set RUN_POSTGRES_TESTS=1 for PostgreSQL temporary tables')
class PostgresClassificacaoTests(unittest.TestCase):
    def setUp(self):
        cfg = dotenv_values(ROOT / '.env')
        self.db_config = dict(
            host=cfg.get('DB_HOST'), port=cfg.get('DB_PORT'), user=cfg.get('DB_USER'),
            password=cfg.get('DB_PASSWORD'), dbname=cfg.get('DB_NAME'), connect_timeout=5,
        )
        self.conn = psycopg2.connect(**self.db_config)
        self.addCleanup(self.conn.close)
        with self.conn.cursor() as cur:
            cur.execute('SET search_path TO pg_temp')
            cur.execute(OLD_SCHEMA)
            cur.execute('SELECT * FROM alertas ORDER BY id_alerta')
            self.before = cur.fetchall()
            cur.execute("SELECT current_schema(), relpersistence FROM pg_class WHERE oid='alertas'::regclass")
            schema, persistence = cur.fetchone()
            self.assertTrue(schema.startswith('pg_temp_'))
            self.assertEqual(persistence, 't')
        self.conn.commit()
        self.apply_migration()
        self.repo = AlertasRepository(self.conn)
        self.service = AlertasService(self.conn)
        app = Flask(__name__)
        app.testing = True
        with patch('controller.alertas_routes.AlertasService', return_value=self.service):
            app.register_blueprint(create_alertas_bp(self.conn))
        self.client = app.test_client()
        self.emit = self.enterContext(patch('services.alertas_service.emitir_evento_global'))
        self.queue = self.enterContext(patch('services.alertas_service.email_queue'))
        self.mqtt = self.enterContext(patch('services.alertas_service.enviar_comando'))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def apply_migration(self):
        with self.conn.cursor() as cur:
            cur.execute(MIGRATION)
        self.conn.commit()

    def create_posture(self, tipo='queda', camera=2, user=4):
        self.assertTrue(self.service.criar_alerta(
            None, user, 'texto independente do tipo', 3 if tipo == 'queda' else 1,
            destinatarios=[4, 5] if user is not None else [], tipo_deteccao=tipo, id_camera=camera,
        ))

    def test_migration_preserves_all_historical_columns_and_marks_unknown_origin(self):
        with self.conn.cursor() as cur:
            cur.execute('SELECT id_alerta, resolvido, data_hora, id_monitorar, id_usuario, evento, severidade FROM alertas ORDER BY id_alerta')
            self.assertEqual(cur.fetchall(), self.before)
            cur.execute('SELECT tipo_deteccao, id_camera FROM alertas ORDER BY id_alerta')
            self.assertEqual(cur.fetchall(), [('legado', None), ('legado', None)])
            cur.execute("INSERT INTO alertas (id_monitorar) VALUES (12) RETURNING tipo_deteccao")
            self.assertEqual(cur.fetchone()[0], 'epi')
        self.conn.commit()
        self.assertEqual(len(self.repo.get_alertas('legado')), 2)

    def test_migration_rolls_back_all_ddl_on_failure_and_rejects_repeat(self):
        # Rebuild ONLY the session-local alertas table to exercise the original schema.
        with self.conn.cursor() as cur:
            cur.execute('DROP TABLE pg_temp.alertas')
            cur.execute(OLD_SCHEMA[OLD_SCHEMA.index('CREATE TEMP TABLE alertas'):OLD_SCHEMA.index('INSERT INTO usuarios')])
            cur.execute('INSERT INTO alertas (id_monitorar) VALUES (12)')
        self.conn.commit()
        with self.assertRaises(psycopg2.errors.DivisionByZero):
            with self.conn.cursor() as cur:
                cur.execute(MIGRATION)
                cur.execute('SELECT 1/0')
        self.conn.rollback()
        with self.conn.cursor() as cur:
            cur.execute("SELECT attname, attnotnull FROM pg_attribute WHERE attrelid='alertas'::regclass AND attnum > 0 AND NOT attisdropped")
            columns = dict(cur.fetchall())
            self.assertNotIn('tipo_deteccao', columns)
            self.assertNotIn('id_camera', columns)
            self.assertTrue(columns['id_monitorar'])
            cur.execute('SELECT count(*) FROM alertas')
            self.assertEqual(cur.fetchone()[0], 1)
        self.conn.commit()
        self.apply_migration()
        with self.assertRaises(psycopg2.errors.DuplicateColumn):
            self.apply_migration()
        self.conn.rollback()
        self.assertEqual(len(self.repo.get_alertas('legado')), 1)

    def test_database_constraints_reject_invalid_types_links_and_foreign_keys(self):
        cases = [
            ('unknown', 12, None), (None, 12, None), ('epi', None, None), ('epi', 12, 2),
            ('queda', 12, 2), ('queda', None, None), ('queda', None, 999),
            ('postura_tronco', None, None), ('postura_rotacao', 12, None),
            ('legado', None, 2), ('epi', 999, None),
        ]
        for tipo, monitoring, camera in cases:
            with self.subTest(tipo=tipo, monitoring=monitoring, camera=camera):
                with self.assertRaises(psycopg2.IntegrityError):
                    with self.conn.cursor() as cur:
                        cur.execute('INSERT INTO alertas (tipo_deteccao, id_monitorar, id_camera) VALUES (%s, %s, %s)',
                                    (tipo, monitoring, camera))
                self.conn.rollback()
        self.assertEqual(len(self.repo.get_alertas()), 2)

    def test_all_reads_include_posture_without_zone_and_filters_do_not_depend_on_text(self):
        self.assertTrue(self.repo.criar_alerta(12, 4, 'texto independente do tipo'))
        for tipo in TIPOS_POSTURA:
            self.create_posture(tipo)
        all_alerts = self.repo.get_alertas()
        self.assertEqual(len(all_alerts), 6)
        self.assertEqual(len(self.repo.get_alertas('legado')), 2)
        self.assertEqual(len(self.repo.get_alertas('epi')), 1)
        self.assertEqual(len(self.repo.get_alertas('postura')), 3)
        self.assertEqual(len(self.repo.get_alertas_por_id_usuario(4)), 5)
        self.assertEqual(len(self.repo.get_alertas_por_id_camera(1)), 3)
        self.assertEqual(len(self.repo.get_alertas_por_id_camera(2, 'postura')), 3)
        self.assertEqual(len(self.repo.get_alertas_por_id_zona(3)), 3)
        self.assertEqual(self.repo.get_alertas_por_id_zona(3, 'postura'), [])
        for tipo in TIPOS_POSTURA:
            result = self.repo.get_alertas(tipo)
            self.assertEqual(len(result), 1)
            detail = self.repo.get_alerta_por_id(result[0].id)
            self.assertEqual(detail, result[0])
            self.assertEqual(detail.id_camera, 2)
            self.assertIsNone(detail.id_monitorar)
            self.assertIsNone(detail.id_zona)
            self.assertIsNone(detail.id_epi)

    def test_flask_lists_detail_filtering_and_existing_empty_http_contract(self):
        for tipo in TIPOS_POSTURA:
            self.create_posture(tipo)
        for route in ('/alertas?tipo=postura', '/alertas/camera/2?tipo=postura'):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertEqual({a['tipo_deteccao'] for a in response.json}, set(TIPOS_POSTURA))
            self.assertTrue(all(a['id_camera'] == 2 and a['id_zona'] is None for a in response.json))
        self.assertEqual(len(self.client.get('/alertas').json), 5)
        for tipo in (*TIPOS_POSTURA, 'legado'):
            response = self.client.get('/alertas', query_string={'tipo': tipo})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(all(a['tipo_deteccao'] == tipo for a in response.json))
        item = self.client.get('/alertas?tipo=queda').json[0]
        self.assertEqual(self.client.get(f"/alertas/{item['id']}").json, item)
        self.assertEqual(set(item), {'id', 'resolvido', 'data', 'id_monitorar', 'id_usuario',
                                     'evento', 'severidade', 'id_zona', 'id_camera', 'id_epi', 'tipo_deteccao'})
        for route in ('/alertas?tipo=epi', '/alertas/camera/999', '/alertas/zona/999',
                      '/alertas/zona/3?tipo=postura', '/alertas/999'):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 404)
                self.assertIn('message', response.json)

    def test_statistics_exclude_legacy_and_posture_only_from_epi_chart(self):
        self.assertEqual(self.client.get('/alertas/estatisticas/epi').json, [])
        self.repo.criar_alerta(12, 4, 'novo EPI')
        self.repo.criar_alerta(13, None, 'zona proibida')
        self.create_posture()
        response = self.client.get('/alertas/estatisticas/epi')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({r['categoria']: r['total'] for r in response.json}, {'Capacete': 1, 'Sem Categoria': 1})
        response = self.client.get('/alertas/estatisticas/periodo?periodo=7')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sum(r['total'] for r in response.json), 5)

    def test_real_insert_precedes_socketio_and_keeps_all_email_recipients(self):
        # Keep a separate Flask app: importing app.py would start unrelated infrastructure.
        app = Flask('classification-socket')
        socketio = SocketIO(app, async_mode='threading')
        client = socketio.test_client(app)
        self.addCleanup(client.disconnect)
        def emit_after_commit(event, payload):
            self.assertEqual(self.conn.get_transaction_status(), psycopg2.extensions.TRANSACTION_STATUS_IDLE)
            socketio.emit(event, payload)
        self.emit.side_effect = emit_after_commit
        self.create_posture()
        messages = client.get_received()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['name'], 'novo_alerta')
        payload = messages[0]['args'][0]
        self.assertEqual(payload['tipo_deteccao'], 'queda')
        self.assertEqual(payload['nome_camera'], 'Sem zonas')
        self.assertEqual(payload['nome_setor'], 'Producao')
        self.assertIsNone(payload['id_monitorar'])
        self.assertEqual(payload['id_usuario'], 4)
        self.assertEqual(len(self.repo.get_alertas('queda')), 1)
        self.assertEqual([c.args[1] for c in self.queue.enqueue.call_args_list],
                         ['test4@example.invalid', 'test5@example.invalid'])

    def test_installation_ddl_matches_migrated_alert_schema(self):
        ddl = (ROOT / 'assets/tabelas_spi-postgres.sql').read_text(encoding='utf-8')
        # Never execute installation DROP statements, even in a temporary search_path.
        ddl = '\n'.join(line for line in ddl.splitlines() if not line.startswith('DROP TABLE'))
        ddl = ddl.replace('CREATE TABLE ', 'CREATE TEMP TABLE ')
        self.assertNotIn('DROP TABLE', ddl)
        fresh = psycopg2.connect(**self.db_config)
        self.addCleanup(fresh.close)
        with fresh.cursor() as cur:
            cur.execute('SET search_path TO pg_temp')
            cur.execute(ddl)
            cur.execute("SELECT relpersistence FROM pg_class WHERE oid='alertas'::regclass")
            self.assertEqual(cur.fetchone()[0], 't')
        query = """SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
                   WHERE conrelid='alertas'::regclass AND contype='c' ORDER BY conname"""
        with self.conn.cursor() as cur:
            cur.execute(query)
            migrated_checks = cur.fetchall()
        with fresh.cursor() as cur:
            cur.execute(query)
            self.assertEqual(cur.fetchall(), migrated_checks)
            cur.execute("SELECT attname, attnotnull FROM pg_attribute WHERE attrelid='alertas'::regclass AND attname IN ('id_monitorar', 'id_camera', 'tipo_deteccao')")
            self.assertEqual(dict(cur.fetchall()), {'id_monitorar': False, 'id_camera': False, 'tipo_deteccao': True})
        fresh.rollback()

    def test_epi_multiple_responsibles_and_posture_without_responsible_keep_semantics(self):
        self.service.registrar_alertas_com_notificacao_unica(
            Zona(id=3, id_camera=1, id_monitorar=12, nome='Entrada'), [4, 5], 'EPI novo', 3,
        )
        self.assertEqual(len(self.repo.get_alertas('epi')), 2)
        self.assertEqual(self.emit.call_count, 1)
        self.assertEqual(self.emit.call_args.args[1]['id_usuario'], 4)
        self.assertEqual(self.queue.enqueue.call_count, 2)
        self.queue.reset_mock()
        self.create_posture(user=None)
        self.assertIsNone(self.repo.get_alertas('queda')[0].id_usuario)
        self.assertIsNone(self.emit.call_args.args[1]['id_usuario'])
        self.queue.enqueue.assert_not_called()

    def test_invalid_references_rollback_without_notifications_and_connection_recovers(self):
        with self.assertLogs('repository.alertas_repository', level='WARNING'):
            self.assertFalse(self.repo.criar_alerta(None, 4, 'queda', tipo_deteccao='queda', id_camera=999))
            self.assertFalse(self.service.criar_alerta(
                Zona(id=999, nome='Inexistente', id_camera=1, id_monitorar=999), 4, 'zona inexistente', 3,
            ))
            self.assertFalse(self.service.criar_alerta(
                None, 999, 'responsavel inexistente', 3, tipo_deteccao='queda', id_camera=2,
            ))
        self.emit.assert_not_called()
        self.queue.enqueue.assert_not_called()
        self.assertEqual(len(self.repo.get_alertas()), 2)
        self.create_posture()
        self.assertEqual(len(self.repo.get_alertas('queda')), 1)

    def test_missing_camera_and_invalid_creation_types_do_not_create_business_data(self):
        with self.assertRaises(ValueError):
            self.service.criar_alerta(None, 4, 'queda', tipo_deteccao='queda', id_camera=999)
        for tipo in ('legado', 'postura', 'abc', "epi' OR 1=1 --"):
            with self.assertRaises(ValueError):
                self.repo.criar_alerta(12, 4, 'evento', tipo_deteccao=tipo)
        self.emit.assert_not_called()
        self.queue.enqueue.assert_not_called()
        self.assertEqual(len(self.repo.get_alertas()), 2)

    def test_resolve_posture_without_alarm_and_epi_with_reset_and_missing_id(self):
        self.create_posture()
        posture = self.repo.get_alertas('queda')[0]
        with patch.object(self.service.monitoramento_repository, 'get_alarme_por_id_monitorar') as lookup:
            self.assertEqual(self.client.put(f'/alertas/{posture.id}/resolvido').status_code, 200)
            lookup.assert_not_called()
        self.mqtt.assert_not_called()
        self.assertTrue(self.repo.get_alerta_por_id(posture.id).resolvido)
        self.repo.criar_alerta(12, 4, 'epi')
        epi = self.repo.get_alertas('epi')[0]
        self.assertEqual(self.client.put(f'/alertas/{epi.id}/resolvido').status_code, 200)
        self.mqtt.assert_called_once_with(comando='RESET', endereco_esp32='test-device')
        self.mqtt.reset_mock()
        self.assertEqual(self.client.put('/alertas/999/resolvido').status_code, 400)
        self.mqtt.assert_not_called()
        self.assertEqual(self.client.delete(f'/alertas/{posture.id}').status_code, 200)
        self.assertIsNone(self.repo.get_alerta_por_id(posture.id))

    def test_posture_camera_foreign_key_prevents_deletion_of_its_origin(self):
        self.create_posture()
        with self.assertRaises(psycopg2.IntegrityError):
            with self.conn.cursor() as cur:
                cur.execute('DELETE FROM cameras WHERE id_camera = 2')
        self.conn.rollback()
        self.assertEqual(self.repo.get_alertas('queda')[0].id_camera, 2)

    def test_real_vision_registration_works_for_camera_with_no_zones(self):
        vision = VisaoService.__new__(VisaoService)
        vision.connection = self.conn
        vision.redis_client = Mock()
        vision.redis_client.set.return_value = True
        vision.setores_repository = SetoresRepository(self.conn)
        vision.alertas_service = self.service
        vision._zonas_de_monitoramento = Mock(side_effect=AssertionError('No arbitrary zones'))
        vision._registrar_alerta_postura(2, 10, 'queda', 3, tipo_deteccao='queda')
        self.assertEqual(len(self.repo.get_alertas_por_id_camera(2, 'queda')), 1)
        vision._zonas_de_monitoramento.assert_not_called()
        self.assertEqual(self.queue.enqueue.call_count, 2)
        with self.assertLogs('services.visao_service', level='WARNING'):
            vision._registrar_alerta_postura(999, 10, 'queda', 3, tipo_deteccao='queda')
        self.assertEqual(len(self.repo.get_alertas('queda')), 1)
