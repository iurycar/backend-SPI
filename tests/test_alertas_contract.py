import contextlib
import io
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, call, patch

from flask import Flask
from flask_socketio import SocketIO

from controller.alertas_routes import create_alertas_bp
from models.zonas import Zona
from services.alertas_service import AlertasService


class AlertPayloadTests(unittest.TestCase):
    def setUp(self):
        self.service = AlertasService(None)
        self.service.alertas_repository = Mock()
        self.service.alertas_repository.criar_alerta.return_value = True
        self.service.cameras_service = Mock()
        self.service.cameras_service.obter_camera_por_id.return_value = {'nome': 'Entrada'}
        self.service.setores_service = Mock()
        self.service.setores_service.obter_setor_por_id_zona.return_value = {'nome': 'Fabrica'}
        self.service._enviar_email_alerta_critico = Mock()
        self.zone = Zona(id=3, nome='Zona teste', id_camera=1, id_monitorar=12)
        self.emitter = self.enterContext(patch('services.alertas_service.emitir_evento_global'))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def test_both_paths_preserve_legacy_fields_and_use_real_zone_id(self):
        self.service.registrar_alertas_com_notificacao_unica(self.zone, [4], 'evento', 2)
        first = self.emitter.call_args.args[1]
        self.service.criar_alerta(self.zone, 4, 'evento', 2)
        second = self.emitter.call_args.args[1]
        self.assertEqual(first, second)
        self.assertEqual(first, {
            'id_monitorar': 12, 'id_camera': 1, 'id_zona': 3, 'id_usuario': 4,
            'nome_zona': 'Zona teste', 'nome_camera': 'Entrada', 'nome_setor': 'Fabrica',
            'evento': 'evento', 'severidade': 2, 'tipo_deteccao': 'epi',
        })
        self.service.setores_service.obter_setor_por_id_zona.assert_called_with(3)

    def test_multiple_responsibles_keep_one_event_and_email_each_recipient(self):
        self.service.registrar_alertas_com_notificacao_unica(self.zone, [4, 5], 'evento', 3)
        self.service.alertas_repository.criar_alerta.assert_has_calls([
            call(12, 4, 'evento', 3, tipo_deteccao='epi'),
            call(12, 5, 'evento', 3, tipo_deteccao='epi'),
        ])
        self.emitter.assert_called_once()
        self.assertEqual(self.emitter.call_args.args[1]['id_usuario'], 4)
        self.assertEqual([c.args[0] for c in self.service._enviar_email_alerta_critico.call_args_list], [4, 5])

    def test_first_successful_record_is_referenced(self):
        self.service.alertas_repository.criar_alerta.side_effect = [False, True]
        self.service.registrar_alertas_com_notificacao_unica(self.zone, [4, 5], 'evento', 3)
        self.assertEqual(self.emitter.call_args.args[1]['id_usuario'], 5)
        self.service._enviar_email_alerta_critico.assert_called_once()
        self.assertEqual(self.service._enviar_email_alerta_critico.call_args.args[0], 5)

    def test_missing_responsible_is_explicit_null_in_socketio_message(self):
        app = Flask(__name__)
        socketio = SocketIO(app, async_mode='threading')
        client = socketio.test_client(app)
        self.addCleanup(client.disconnect)
        with patch('services.alertas_service.emitir_evento_global', side_effect=socketio.emit):
            self.service.registrar_alertas_com_notificacao_unica(self.zone, [], 'evento')
        self.service.alertas_repository.criar_alerta.assert_called_once_with(
            12, None, 'evento', 1, tipo_deteccao='epi'
        )
        events = client.get_received()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['name'], 'novo_alerta')
        self.assertIn('id_usuario', events[0]['args'][0])
        self.assertIsNone(events[0]['args'][0]['id_usuario'])

    def test_failed_insert_never_emits_or_sends_email(self):
        self.service.alertas_repository.criar_alerta.return_value = False
        for recipients in ([], [4], [4, 5]):
            self.assertFalse(self.service.registrar_alertas_com_notificacao_unica(self.zone, recipients, 'evento', 3))
        self.assertFalse(self.service.criar_alerta(self.zone, 4, 'evento', 3))
        self.emitter.assert_not_called()
        self.service._enviar_email_alerta_critico.assert_not_called()

    def test_dict_monitoring_preserves_ids_in_both_paths(self):
        for zone_key in ('id', 'id_zona'):
            zone = {zone_key: 3, 'nome': 'Zona teste', 'id_camera': 1, 'id_monitorar': 12}
            self.service.registrar_alertas_com_notificacao_unica(zone, [4], 'evento')
            first = self.emitter.call_args.args[1]
            self.service.criar_alerta(zone, 4, 'evento')
            self.assertEqual(first, self.emitter.call_args.args[1])
            self.assertEqual(first['id_zona'], 3)
            self.assertEqual(first['id_camera'], 1)

    def test_single_record_keeps_all_email_recipients(self):
        self.service.criar_alerta(self.zone, 4, 'evento', 3, destinatarios=[4, 5])
        self.service.alertas_repository.criar_alerta.assert_called_once_with(
            12, 4, 'evento', 3, tipo_deteccao='epi', id_camera=None
        )
        self.emitter.assert_called_once()
        self.assertEqual([c.args[0] for c in self.service._enviar_email_alerta_critico.call_args_list], [4, 5])


class PeriodRouteTests(unittest.TestCase):
    def setUp(self):
        service = AlertasService(None)
        self.repo = service.alertas_repository = Mock()
        self.repo.get_contagem_por_periodo.return_value = [{'dia': '2026-09-10', 'total': 2}]
        self.repo.get_contagem_por_tipo_epi.return_value = [{'categoria': 'Capacete', 'total': 2}]
        app = Flask(__name__)
        app.testing = True
        with patch('controller.alertas_routes.AlertasService', return_value=service):
            app.register_blueprint(create_alertas_bp(None))
        self.client = app.test_client()

    def test_default_and_explicit_days_reach_repository_as_correct_date(self):
        for suffix, days in [('', 30), ('?periodo=7', 7), ('?periodo=1', 1)]:
            with self.subTest(suffix=suffix):
                before = datetime.now() - timedelta(days=days)
                response = self.client.get('/alertas/estatisticas/periodo' + suffix)
                after = datetime.now() - timedelta(days=days)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, [{'dia': '2026-09-10', 'total': 2}])
                cutoff = self.repo.get_contagem_por_periodo.call_args.args[0]
                self.assertLessEqual(before, cutoff)
                self.assertLessEqual(cutoff, after)

    def test_invalid_days_return_json_400_without_querying_database(self):
        for value in ('abc', '', '0', '-1', '1.5', '1e3', '999999999999999999999'):
            with self.subTest(value=value):
                response = self.client.get('/alertas/estatisticas/periodo', query_string={'periodo': value})
                self.assertEqual(response.status_code, 400)
                self.assertIn('message', response.json)
        self.repo.get_contagem_por_periodo.assert_not_called()

    def test_no_alerts_still_returns_empty_array(self):
        self.repo.get_contagem_por_periodo.return_value = []
        response = self.client.get('/alertas/estatisticas/periodo?periodo=7')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])

    def test_epi_statistics_contract_is_preserved(self):
        response = self.client.get('/alertas/estatisticas/epi')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [{'categoria': 'Capacete', 'total': 2}])
