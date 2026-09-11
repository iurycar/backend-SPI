import contextlib
import io
import json
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import numpy as np
from flask import Flask

from core.vision_metrics import FrameMetrics, detection_snapshot, processing_fps
from core.alerta_diagnostics import trace_alert_candidate
from controller import visao_routes, cameras_routes, zonas_routes
from worker import vision_manager
from worker.vision_worker import VisionWorker
from services.visao_service import VisaoService
from services.zonas_service import ZonasService
from repository.zonas_repository import ZonasRepository


class MetricsTests(unittest.TestCase):
    def test_known_rate_latency_and_window(self):
        metrics = FrameMetrics()
        for i in range(31):
            t = 100 + i / 10
            result = metrics.complete(t - .046, t)
        self.assertEqual(processing_fps(result['completions'], 103), 10)
        self.assertEqual(result['latencia_ms'], 46)
        self.assertEqual(processing_fps(result['completions'], 107), 0)
        self.assertEqual(processing_fps([100], 100), 0)

    def test_disconnection_and_stale_result_clear_metrics(self):
        result = dict(FrameMetrics().complete(99.9, 100), detections=[{'id': 7}])
        for connected, now in [(False, 100), (True, 106)]:
            snapshot = detection_snapshot(result, connected, now)
            self.assertEqual(snapshot['connected'], connected)
            self.assertEqual(snapshot['detections'], [])
            self.assertEqual(snapshot['fps'], 0)
            self.assertIsNone(snapshot['latencia_ms'])

    def test_polling_is_read_only_and_cameras_are_independent(self):
        first, second = FrameMetrics(), FrameMetrics()
        for i in range(21):
            a = first.complete(100 + i / 10 - .05, 100 + i / 10)
        for i in range(5):
            b = second.complete(100 + i / 2 - .1, 100 + i / 2)
        for _ in range(10):
            self.assertEqual(detection_snapshot(a, True, 102)['fps'], 10)
            self.assertEqual(detection_snapshot(b, True, 102)['fps'], 2)
        self.assertEqual(len(a['completions']), 21)


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.camera_service = Mock()
        with patch.object(cameras_routes, 'CamerasService', return_value=cls.camera_service):
            cls.app.register_blueprint(cameras_routes.create_cameras_bp(None))
        cls.app.register_blueprint(visao_routes.create_visao_bp(None))
        cls.client = cls.app.test_client()

    def setUp(self):
        vision_manager.workers.clear()
        self.addCleanup(vision_manager.workers.clear)

    def worker(self, online=True):
        worker = VisionWorker.__new__(VisionWorker)
        worker.cameras = [1, 2]
        worker.process = Mock()
        worker.process.is_alive.return_value = online
        now = time.monotonic()
        worker.last_results = {
            1: {'connected': True, 'last_frame_time': time.time(),
                'result': dict(FrameMetrics().complete(now - .03, now),
                               detections=[{'id': 101}], class_count={'pessoa': 1})},
            2: {'connected': False, 'last_frame_time': 0, 'result': {}},
        }
        return worker

    def test_missing_worker_contract_does_not_depend_on_other_cameras(self):
        empty = self.client.get('/detections/1')
        vision_manager.workers[2] = self.worker()
        other = self.client.get('/detections/1')
        self.assertEqual(empty.status_code, 503)
        self.assertEqual(empty.json, other.json)
        self.assertEqual(set(empty.json), {'detections', 'class_count', 'connected', 'fps', 'latencia_ms', 'message'})

    def test_batch_isolation_and_dead_process(self):
        worker = self.worker()
        vision_manager.workers.update({1: worker, 2: worker})
        self.assertEqual(self.client.get('/detections/1').json['detections'], [{'id': 101}])
        self.assertFalse(self.client.get('/detections/2').json['connected'])
        worker.process.is_alive.return_value = False
        self.assertEqual(self.client.get('/detections/1').json['detections'], [])

    def test_camera_status_includes_registered_inactive_cameras(self):
        worker = self.worker()
        vision_manager.workers.update({1: worker, 2: worker})
        self.camera_service.listar_cameras.return_value = [
            {'id': i, 'nome': str(i), 'ip': 'test', 'id_setor': 1} for i in (1, 2, 3)]
        response = self.client.get('/cameras/status')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c['status'] for c in response.json], ['Ativo', 'Desconectado', 'Inativo'])
        worker.last_results[1]['last_frame_time'] = time.time() - 6
        self.assertEqual(vision_manager.get_camera_status(1), 'Desconectado')


class ZoneTests(unittest.TestCase):
    def test_failed_monitoring_insert_rolls_back_zone(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (5, 'new', 0, 0, 1, 1, False, 1)
        cursor.execute.side_effect = [None, RuntimeError('monitoring insert failed')]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(ZonasRepository(conn).registrar_zona('new', 1))
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()

    def test_registration_passes_epi_and_notifies_only_after_success(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (5, 'new', 0, 0, 1, 1, False, 1)
        app = Flask(__name__)
        app.register_blueprint(zonas_routes.create_zonas_bp(conn))
        with patch('services.zonas_service.redis_client') as cache, patch.object(zonas_routes, 'notificar_atualizacao_zonas') as notify:
            response = app.test_client().post('/zonas/registrar', json={'nome': 'new', 'id_camera': 1, 'id_epi': 8, 'permitido': False})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(cursor.execute.call_args.args[1], (5, 8))
            conn.commit.assert_called_once()
            cache.delete.assert_called_once_with('cache:zonas:camera:1')
            notify.assert_called_once_with(1)
            cursor.execute.side_effect = RuntimeError('insert failed')
            notify.reset_mock()
            with contextlib.redirect_stdout(io.StringIO()):
                response = app.test_client().post('/zonas/registrar', json={'nome': 'new', 'id_camera': 1})
            self.assertEqual(response.status_code, 400)
            notify.assert_not_called()


class DiagnosticTests(unittest.TestCase):
    def test_diagnostic_is_opt_in_and_records_track_and_decision(self):
        output = io.StringIO()
        with patch.dict('os.environ', {'ALERT_DIAGNOSTICS': 'false'}), contextlib.redirect_stdout(output):
            trace_alert_candidate('epi', 1, 2, 'event', 7, True)
        self.assertEqual(output.getvalue(), '')
        with patch.dict('os.environ', {'ALERT_DIAGNOSTICS': 'true'}), contextlib.redirect_stdout(output):
            trace_alert_candidate('epi', 1, 2, 'event', 7, False)
        self.assertEqual(json.loads(output.getvalue())['track_id'], 7)
        self.assertFalse(json.loads(output.getvalue())['cooldown_acquired'])

    def test_existing_lock_granularity_is_preserved_in_both_paths(self):
        service = VisaoService.__new__(VisaoService)
        service.redis_client = Mock()
        service.redis_client.set.return_value = False
        zone = SimpleNamespace(id=4, id_camera=2, id_monitorar=9)
        service._registrar_alerta_epi_incorreto(zone, 'event', 7)
        service.redis_client.set.assert_called_with('lock:alerta:epi:9:event:7', '1', ex=30, nx=True)
        service._registrar_alerta_postura(2, 7, 'fall', severidade=3, tipo_deteccao='queda')
        service.redis_client.set.assert_called_with('lock:alerta:postura:2:7:fall', '1', ex=30, nx=True)


class BatchLoopTests(unittest.TestCase):
    def test_single_captured_frame_is_not_reprocessed(self):
        stop = threading.Event()
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        class Capture:
            first = True
            def isOpened(self): return True
            def read(self):
                if self.first:
                    self.first = False
                    return True, frame
                stop.wait(1)
                return False, None
            def release(self): pass
        service = VisaoService.__new__(VisaoService)
        service._ensure_models_loaded = Mock()
        service._zonas_de_monitoramento = Mock(return_value=[])
        service.open_camera = Mock(return_value=Capture())
        service._batch_object_detection = Mock(return_value=([[{'id': 1}]], [{'pessoa': 1}]))
        service._batch_pose_estimation = Mock()
        service._desenhar_hud_topo = Mock()
        results = {1: {}}
        timer = threading.Timer(.2, stop.set)
        timer.start()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                service.run_batch_video_loop([1], {}, results, stop, {})
        finally:
            stop.set()
            timer.join()
        service._batch_object_detection.assert_called_once()
        self.assertEqual(len(results[1]['result']['completions']), 1)
        self.assertEqual(results[1]['result']['detections'], [{'id': 1}])
        self.assertGreaterEqual(results[1]['result']['latencia_ms'], 0)


if __name__ == '__main__':
    unittest.main()
