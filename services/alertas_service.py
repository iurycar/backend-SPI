from repository.alertas_repository import AlertasRepository
from services.usuario_service import UsuarioService
from services.cameras_service import CamerasService
from services.setores_service import SetoresService

from extensions import emitir_evento_global

from datetime import datetime, timedelta

from models.cameras import Camera
from models.setores import Setor
from models.zonas import Zona

from tasks.email_task import task_enviar_email_alerta_critico
from extensions import redis_client, emitir_evento_global
from rq import Queue

from email.message import EmailMessage
import smtplib
import os

email_queue = Queue('emails', connection=redis_client)  # Cria uma fila de tarefas para envio de e-mails

class AlertasService:
    def __init__(self, connection):
        self.connection = connection
        self.alertas_repository = AlertasRepository(connection)
        self.usuario_service = UsuarioService(connection)
        self.cameras_service = CamerasService(connection)
        self.setores_service = SetoresService(connection)

    def obter_alertas(self) -> list[dict] | None:
        alertas = self.alertas_repository.get_alertas()

        alertas_lista: list[dict] = []

        if alertas:
            for alerta in alertas:
                alertas_dict = {
                    'id': alerta.id,
                    'resolvido': alerta.resolvido,
                    'data': alerta.data_hora,
                    'id_monitorar': alerta.id_monitorar,
                    'id_usuario': alerta.id_usuario,
                    'evento': alerta.evento,
                    'severidade': alerta.severidade,
                    'id_zona': alerta.id_zona,
                    'id_camera': alerta.id_camera,
                    'id_epi': alerta.id_epi
                }
                alertas_lista.append(alertas_dict)

        return alertas_lista

    def obter_alertas_por_id_camera(self, camera_id: int) -> list[dict]:
        alertas = self.alertas_repository.get_alertas_por_id_camera(camera_id)

        alertas_lista: list[dict] = []

        if alertas:
            for alerta in alertas:
                alertas_dict = {
                    'id': alerta.id,
                    'resolvido': alerta.resolvido,
                    'data': alerta.data_hora,
                    'id_monitorar': alerta.id_monitorar,
                    'id_usuario': alerta.id_usuario,
                    'evento': alerta.evento,
                    'severidade': alerta.severidade,
                    'id_zona': alerta.id_zona,
                    'id_camera': alerta.id_camera,
                    'id_epi': alerta.id_epi
                }
                alertas_lista.append(alertas_dict)

        return alertas_lista

    def obter_alertas_por_id_zona(self, zona_id: int) -> list[dict]:
        alertas = self.alertas_repository.get_alertas_por_id_zona(zona_id)

        alertas_lista: list[dict] = []

        if alertas:
            for alerta in alertas:
                alertas_dict = {
                    'id': alerta.id,
                    'resolvido': alerta.resolvido,
                    'data': alerta.data_hora,
                    'id_monitorar': alerta.id_monitorar,
                    'id_usuario': alerta.id_usuario,
                    'evento': alerta.evento,
                    'severidade': alerta.severidade,
                    'id_zona': alerta.id_zona,
                    'id_camera': alerta.id_camera,
                    'id_epi': alerta.id_epi
                }
                alertas_lista.append(alertas_dict)

        return alertas_lista

    def obter_alerta_por_id(self, alerta_id: int) -> dict | None:
        alerta = self.alertas_repository.get_alerta_por_id(alerta_id)

        if alerta:
            alerta_dict = {
                'id': alerta.id,
                'resolvido': alerta.resolvido,
                'data': alerta.data_hora,
                'id_monitorar': alerta.id_monitorar,
                'id_usuario': alerta.id_usuario,
                'evento': alerta.evento,
                'severidade': alerta.severidade,
                'id_zona': alerta.id_zona,
                'id_camera': alerta.id_camera,
                'id_epi': alerta.id_epi
            }
            return alerta_dict

        return None

    def marcar_alerta_resolvido(self, id_alerta: int) -> bool:
        return self.alertas_repository.marcar_alerta_resolvido(id_alerta)

    def criar_alerta(self, monitoramento: Zona | dict, id_usuario: int | None, evento: str, severidade: int = 1) -> bool:
        sucesso = self.alertas_repository.criar_alerta(monitoramento.id_monitorar, id_usuario, evento, severidade)

        if not sucesso:
            return False

        # Ambos retornam dicionários (dict) ou None
        camera_dict = self.cameras_service.obter_camera_por_id(monitoramento.id_camera)
        setor_dict = self.setores_service.obter_setor_por_id_zona(monitoramento.id)

        # Use .get() para dicionários
        nome_camera = camera_dict.get('nome') if camera_dict else None
        nome_setor = setor_dict.get('nome') if setor_dict else None

        # Se monitoramento for uma classe Zona: monitoramento.nome
        # Se monitoramento vier como dict: monitoramento.get('nome')
        nome_zona = getattr(monitoramento, 'nome', None) or (monitoramento.get('nome') if isinstance(monitoramento, dict) else None)
        id_monitorar = getattr(monitoramento, 'id_monitorar', None) or (monitoramento.get('id_monitorar') if isinstance(monitoramento, dict) else None)
        id_camera = getattr(monitoramento, 'id_camera', None) or (monitoramento.get('id_camera') if isinstance(monitoramento, dict) else None)
        id_zona = getattr(monitoramento, 'id_zona', None) or (monitoramento.get('id_zona') if isinstance(monitoramento, dict) else None)

        payload_notificao = {
            'id_monitorar': id_monitorar,
            'id_camera': id_camera,
            'id_zona': id_zona,
            'id_usuario': id_usuario,
            'nome_zona': nome_zona,
            'nome_camera': nome_camera,
            'nome_setor': nome_setor,
            'evento': evento,
            'severidade': severidade
        }

        print(f"Alerta criado: {payload_notificao}")
        emitir_evento_global('novo_alerta', payload_notificao)

        if severidade == 3 and id_usuario:
            self._enviar_email_alerta_critico(id_usuario, nome_zona, nome_camera, nome_setor, evento, severidade)

        return True

    def _enviar_email_alerta_critico(self, id_usuario: int, nome_zona: str, nome_camera: str, nome_setor: str, evento: str, severidade: int):
        email = self.usuario_service.obter_email_usuario_por_id(id_usuario)
        
        if email:
            email_queue.enqueue(
                task_enviar_email_alerta_critico,
                email,
                nome_zona,
                nome_camera,
                nome_setor,
                evento,
                severidade
            )

    def deletar_alerta(self, id_alerta: int) -> bool:
        return self.alertas_repository.deletar_alerta(id_alerta)

    def obter_contagem_alertas_por_epi(self) -> list[dict]:
        return self.alertas_repository.get_contagem_alertas_por_epi()

    def obter_contagem_por_dia(self, dias: int = 30) -> list[dict]:
        desde = datetime.now() - timedelta(days=dias)
        return self.alertas_repository.get_contagem_por_dia(desde)