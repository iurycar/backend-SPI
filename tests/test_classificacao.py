import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

import numpy as np
from flask import Flask
from flask_socketio import SocketIO

from controller.alertas_routes import create_alertas_bp
from core.tipo_deteccao import TIPOS_POSTURA
from models.zonas import Zona
from services.alertas_service import AlertasService
from services.visao_service import VisaoService


class ClassificacaoServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AlertasService(None)
        self.service.alertas_repository = Mock()
        self.service.alertas_repository.criar_alerta.return_value = True
        self.service.cameras_service = Mock()
        self.service.cameras_service.obter_camera_por_id.return_value = {
            'id': 2, 'nome': 'Camera sem zonas', 'id_setor': 7,
        }
        self.service.setores_service = Mock()
        self.service.setores_service.obter_setor_por_id.return_value = {'id': 7, 'nome': 'Producao'}
        self.service._enviar_email_alerta_critico = Mock()
        self.emit = self.enterContext(patch('services.alertas_service.emitir_evento_global'))

    def test_posture_socket_payload_has_camera_context_and_all_previous_keys(self):
        app = Flask(__name__)
        socketio = SocketIO(app, async_mode='threading')
        client = socketio.test_client(app)
        self.addCleanup(client.disconnect)
        self.emit.side_effect = socketio.emit
        for tipo in TIPOS_POSTURA:
            with self.subTest(tipo=tipo):
                self.assertTrue(self.service.criar_alerta(
                    None, 4, 'mesmo texto', 3, destinatarios=[4, 5],
                    tipo_deteccao=tipo, id_camera=2,
                ))
                messages = client.get_received()
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0]['name'], 'novo_alerta')
                self.assertEqual(messages[0]['args'][0], {
                    'id_monitorar': None, 'id_usuario': 4, 'id_camera': 2,
                    'id_zona': None, 'nome_zona': None, 'nome_camera': 'Camera sem zonas',
                    'nome_setor': 'Producao', 'evento': 'mesmo texto',
                    'severidade': 3, 'tipo_deteccao': tipo,
                })
        self.service.setores_service.obter_setor_por_id_zona.assert_not_called()
        self.assertEqual(self.service.alertas_repository.criar_alerta.call_count, 3)
        self.assertEqual([c.args[0] for c in self.service._enviar_email_alerta_critico.call_args_list],
                         [4, 5, 4, 5, 4, 5])

    def test_no_responsibles_persists_and_emits_null_user_without_email(self):
        self.service.criar_alerta(None, None, 'queda', 3, tipo_deteccao='queda', id_camera=2)
        self.service.alertas_repository.criar_alerta.assert_called_once_with(
            None, None, 'queda', 3, tipo_deteccao='queda', id_camera=2,
        )
        self.assertIsNone(self.emit.call_args.args[1]['id_usuario'])
        self.service._enviar_email_alerta_critico.assert_not_called()

    def test_missing_camera_never_inserts_or_notifies(self):
        self.service.cameras_service.obter_camera_por_id.return_value = None
        with self.assertRaises(ValueError):
            self.service.criar_alerta(None, 4, 'queda', 3, tipo_deteccao='queda', id_camera=999)
        self.service.alertas_repository.criar_alerta.assert_not_called()
        self.emit.assert_not_called()
        self.service._enviar_email_alerta_critico.assert_not_called()

    def test_invalid_types_and_links_fail_before_insert(self):
        zone = Zona(id=3, nome='Entrada', id_camera=2, id_monitorar=12)
        cases = [
            (None, 'postura', 2), (None, 'legado', 2), (None, 'QUEDA', 2),
            (None, 'queda', None), (None, 'queda', 0), (None, 'queda', True),
            (zone, 'queda', 2), ({'id_zona': 3}, 'queda', 2),
            (None, 'epi', None), (zone, 'epi', 2),
        ]
        for monitoring, tipo, camera in cases:
            with self.subTest(tipo=tipo, camera=camera, monitoring=monitoring):
                with self.assertRaises(ValueError):
                    self.service.criar_alerta(monitoring, 4, 'evento', tipo_deteccao=tipo, id_camera=camera)
        for tipo in ('legado', 'postura', 'queda', ''):
            with self.assertRaises(ValueError):
                self.service.registrar_alertas_com_notificacao_unica(zone, [4], 'evento', tipo_deteccao=tipo)
        self.service.alertas_repository.criar_alerta.assert_not_called()
        self.emit.assert_not_called()

    def test_failed_posture_insert_never_notifies(self):
        self.service.alertas_repository.criar_alerta.return_value = False
        self.assertFalse(self.service.criar_alerta(
            None, 4, 'queda', 3, destinatarios=[4, 5], tipo_deteccao='queda', id_camera=2,
        ))
        self.emit.assert_not_called()
        self.service._enviar_email_alerta_critico.assert_not_called()


class ClassificacaoRouteTests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        app = Flask(__name__)
        app.testing = True
        with patch('controller.alertas_routes.AlertasService', return_value=self.service):
            app.register_blueprint(create_alertas_bp(None))
        self.client = app.test_client()

    def test_invalid_or_repeated_filters_return_400_without_service_calls(self):
        values = ['', 'desconhecido', 'QUEDA', ' queda', 'queda ', 'null', "epi' OR 1=1 --"]
        for route in ('/alertas', '/alertas/camera/1', '/alertas/zona/1'):
            for value in values:
                with self.subTest(route=route, value=value):
                    result = self.client.get(route, query_string={'tipo': value})
                    self.assertEqual(result.status_code, 400)
                    self.assertIn('message', result.json)
            for query in ('tipo=epi&tipo=queda', 'tipo=queda&tipo=queda'):
                self.assertEqual(self.client.get(route + '?' + query).status_code, 400)
        self.assertEqual(self.service.mock_calls, [])


class ClassificacaoVisionTests(unittest.TestCase):
    def setUp(self):
        self.service = VisaoService.__new__(VisaoService)
        self.service.redis_client = Mock()
        self.service.redis_client.set.return_value = True
        self.service.setores_repository = Mock()
        self.service.setores_repository.get_setor_por_id_camera.return_value = SimpleNamespace(id=7)
        self.service.setores_repository.get_responsaveis_por_setor.return_value = [4, 5]
        self.service.alertas_service = Mock()
        self.service._zonas_de_monitoramento = Mock(side_effect=AssertionError('Posture must not use zones'))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def test_posture_registration_is_independent_of_zones_and_keeps_recipients(self):
        self.service._registrar_alerta_postura(2, 10, 'queda', 3, tipo_deteccao='queda')
        self.service.alertas_service.criar_alerta.assert_called_once_with(
            monitoramento=None, id_usuario=4, evento='queda', severidade=3,
            destinatarios=[4, 5], tipo_deteccao='queda', id_camera=2,
        )
        self.service.redis_client.set.assert_called_once_with('lock:alerta:postura:2:10:queda', '1', ex=30, nx=True)
        self.service._zonas_de_monitoramento.assert_not_called()

    def test_missing_camera_is_logged_and_next_camera_can_still_register(self):
        self.service.setores_repository.get_setor_por_id_camera.side_effect = [None, SimpleNamespace(id=7)]
        with self.assertLogs('services.visao_service', level='WARNING'):
            self.service._registrar_alerta_postura(999, 10, 'queda', 3, tipo_deteccao='queda')
        self.service.alertas_service.criar_alerta.assert_not_called()
        self.service._registrar_alerta_postura(2, 10, 'queda', 3, tipo_deteccao='queda')
        self.service.alertas_service.criar_alerta.assert_called_once()

    def test_no_responsibles_or_stale_camera_context_does_not_crash_worker(self):
        self.service.setores_repository.get_responsaveis_por_setor.return_value = None
        self.service._registrar_alerta_postura(2, 10, 'queda', 3, tipo_deteccao='queda')
        self.assertIsNone(self.service.alertas_service.criar_alerta.call_args.kwargs['id_usuario'])
        self.service.alertas_service.criar_alerta.side_effect = ValueError('Camera removed')
        with self.assertLogs('services.visao_service', level='WARNING'):
            self.service._registrar_alerta_postura(2, 10, 'queda', 3, tipo_deteccao='queda')

    def test_rejected_cooldown_has_no_persistence(self):
        self.service.redis_client.set.return_value = False
        self.service._registrar_alerta_postura(2, 10, 'queda', 3, tipo_deteccao='queda')
        self.service.alertas_service.criar_alerta.assert_not_called()
        self.service.setores_repository.get_setor_por_id_camera.assert_not_called()

    def test_pose_branches_supply_types_without_inspecting_event_text_and_skip_unknown_track(self):
        self.service._ensure_models_loaded = Mock()
        result = MagicMock()
        result.keypoints.__len__.return_value = 1
        result.keypoints.xy.cpu.return_value.numpy.return_value = np.full((1, 17, 2), 10.0)
        result.boxes.id.int.return_value.cpu.return_value.tolist.return_value = [10]
        self.service.modelo_pose = Mock()
        self.service.modelo_pose.track.return_value = [result]
        self.service._avaliar_postura = Mock(return_value=(True, 'mesmo texto', (10, 10), (20, 20)))
        self.service._registrar_alerta_postura = Mock()
        self.service._batch_pose_estimation([np.zeros((32, 32, 3), dtype=np.uint8)], [2])
        self.assertEqual(self.service._registrar_alerta_postura.call_args_list, [
            call(2, 10, 'mesmo texto', tipo_deteccao='postura_tronco'),
            call(2, 10, 'mesmo texto', tipo_deteccao='postura_rotacao'),
            call(2, 10, 'mesmo texto', severidade=3, tipo_deteccao='queda'),
        ])
        self.service._registrar_alerta_postura.reset_mock()
        result.boxes.id = None
        self.service._batch_pose_estimation([np.zeros((32, 32, 3), dtype=np.uint8)], [2])
        self.service._registrar_alerta_postura.assert_not_called()
