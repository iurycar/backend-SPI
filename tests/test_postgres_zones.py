"""Opt-in integration tests. All writes target session-local temporary tables."""
import contextlib
import io
import os
import threading
import time
import numpy as np
import unittest
from unittest.mock import Mock, patch

import psycopg2
from dotenv import dotenv_values
from flask import Flask
from controller import zonas_routes
from services.visao_service import VisaoService
from worker import vision_manager
from worker.vision_worker import VisionWorker
from repository.monitoramento_repository import MonitoramentoRepository


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == '1', 'Set RUN_POSTGRES_TESTS=1 to use PostgreSQL temporary tables')
class PostgresZoneTests(unittest.TestCase):
    def setUp(self):
        cfg = dotenv_values('.env')
        self.conn = psycopg2.connect(host=cfg.get('DB_HOST'), port=cfg.get('DB_PORT'),
                                     user=cfg.get('DB_USER'), password=cfg.get('DB_PASSWORD'),
                                     dbname=cfg.get('DB_NAME'), connect_timeout=5)
        self.addCleanup(self.conn.close)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute("SET search_path TO pg_temp")
            cur.execute("CREATE TEMP TABLE cameras (id_camera integer PRIMARY KEY)")
            cur.execute("CREATE TEMP TABLE epis (id_epi integer PRIMARY KEY, categoria text)")
            cur.execute("""CREATE TEMP TABLE zonas (
                id_zona integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                nome varchar(40) NOT NULL, x numeric NOT NULL, y numeric NOT NULL,
                largura numeric NOT NULL, altura numeric NOT NULL,
                permitido boolean NOT NULL, id_camera integer REFERENCES cameras(id_camera))""")
            cur.execute("""CREATE TEMP TABLE monitorar (
                id_monitorar integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                id_zona integer NOT NULL REFERENCES zonas(id_zona),
                id_epi integer REFERENCES epis(id_epi))""")
            cur.execute("INSERT INTO cameras VALUES (1)")
            cur.execute("INSERT INTO epis VALUES (8, 'capacete')")
        self.conn.autocommit = False
        app = Flask(__name__)
        app.register_blueprint(zonas_routes.create_zonas_bp(self.conn))
        self.client = app.test_client()

    def register(self, **fields):
        payload = dict(nome='test zone', id_camera=1, permitido=False)
        payload.update(fields)
        return self.client.post('/zonas/registrar', json=payload)

    def test_new_zone_is_visible_to_actual_monitoring_query(self):
        with patch('services.zonas_service.redis_client') as cache, patch.object(zonas_routes, 'notificar_atualizacao_zonas') as notify:
            response = self.register()
            self.assertEqual(response.status_code, 201)
            zones = MonitoramentoRepository(self.conn).get_zonas_monitoradas_por_id_camera(1)
            self.assertEqual([z.id for z in zones], [response.json['id']])
            self.assertIsNotNone(zones[0].id_monitorar)
            notify.assert_called_once_with(1)
            cache.delete.assert_called_once_with('cache:zonas:camera:1')

    def test_epi_is_available_to_actual_monitoring_query(self):
        with patch('services.zonas_service.redis_client'), patch.object(zonas_routes, 'notificar_atualizacao_zonas'):
            self.assertEqual(self.register(permitido=True, id_epi=8).status_code, 201)
        zones = MonitoramentoRepository(self.conn).get_zonas_monitoradas_por_id_camera(1)
        self.assertEqual(zones[0].epis_categoria, ['capacete'])

    def test_registration_reloads_zones_before_next_detection(self):
        stop = threading.Event()
        reload_event = threading.Event()
        worker = VisionWorker.__new__(VisionWorker)
        worker.cameras = [1]
        worker.reload_zones_events = {1: reload_event}
        service = VisaoService.__new__(VisaoService)
        service.connection = self.conn
        service.monitoramento_repository = MonitoramentoRepository(self.conn)
        service._ensure_models_loaded = Mock()
        service._batch_pose_estimation = Mock()
        service._desenhar_hud_topo = Mock()
        class Capture:
            def isOpened(self): return True
            def read(self):
                time.sleep(.005)
                return True, np.zeros((8, 8, 3), dtype=np.uint8)
            def release(self): pass
        service.open_camera = Mock(return_value=Capture())
        observed = []
        created = []
        def detect(frames, camera_ids, zones):
            observed.append([zone.id for zone in zones[1]])
            if not created:
                response = self.register()
                self.assertEqual(response.status_code, 201)
                created.append(response.json['id'])
                self.assertTrue(reload_event.is_set())
            else:
                self.assertEqual(observed[-1], created)
                self.assertFalse(reload_event.is_set())
                stop.set()
            return [[] for _ in frames], [{} for _ in frames]
        service._batch_object_detection = detect
        watchdog = threading.Timer(2, stop.set)
        watchdog.start()
        try:
            with patch.dict(vision_manager.workers, {1: worker}, clear=True), patch('services.zonas_service.redis_client'), contextlib.redirect_stdout(io.StringIO()):
                service.run_batch_video_loop([1], {}, {1: {}}, stop, {1: reload_event})
        finally:
            stop.set()
            watchdog.cancel()
            watchdog.join()
        self.assertEqual(observed, [[], created])

    def test_invalid_epi_leaves_neither_zone_nor_monitoring(self):
        with patch('services.zonas_service.redis_client') as cache, patch.object(zonas_routes, 'notificar_atualizacao_zonas') as notify, contextlib.redirect_stdout(io.StringIO()):
            response = self.register(id_epi=999)
        self.assertEqual(response.status_code, 400)
        with self.conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM zonas')
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute('SELECT count(*) FROM monitorar')
            self.assertEqual(cur.fetchone()[0], 0)
        notify.assert_not_called()
        cache.delete.assert_not_called()


if __name__ == '__main__':
    unittest.main()
