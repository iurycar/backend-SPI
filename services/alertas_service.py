from repository.alertas_repository import AlertasRepository
from services.usuario_service import UsuarioService

from email.message import EmailMessage
from datetime import datetime, timedelta
import smtplib
import os

class AlertasService:
    def __init__(self, connection, alertas_queue=None):
        self.connection = connection
        self.alertas_repository = AlertasRepository(connection)
        self.usuario_service = UsuarioService(connection)
        self.alertas_queue = alertas_queue

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

    def criar_alerta(self, id_monitorar: int, id_usuario: int | None, evento: str, severidade: int = 1) -> bool:
        sucesso = self.alertas_repository.criar_alerta(id_monitorar, id_usuario, evento, severidade)

        if not sucesso:
            return False

        alerta_dict = {
            'id_monitorar': id_monitorar,
            'id_usuario': id_usuario,
            'evento': evento,
            'severidade': severidade,
        }

        # Emite o alerta para os clientes conectados via WebSocket. Como a criação
        # do alerta pode acontecer dentro do subprocesso do VisionWorker, o evento
        # é colocado numa fila multiprocessing e um listener no processo principal
        # (onde o SocketIO de fato roda) é quem repassa para socketio.emit(...).
        if self.alertas_queue is not None:
            try:
                self.alertas_queue.put_nowait(alerta_dict)
            except Exception:
                pass

        if severidade == 3:
            self._enviar_email_alerta_critico(id_monitorar, id_usuario, evento, severidade)

        return True

    def _enviar_email_alerta_critico(self, id_monitorar: int, id_usuario: int | None, evento: str, severidade: int) -> None:
        email = self.usuario_service.get_email_usuario_por_id(id_usuario)

        if not email:
            return

        email_address = os.getenv('EMAIL_ADDRESS')
        token_senha = os.getenv('EMAIL_PASSWORD')

        if not (email_address and token_senha):
            return

        msg = EmailMessage()

        corpo_email = f"Alerta de severidade crítico, na zona de monitoramento {id_monitorar}!\n\nEvento: {evento}\nSeveridade: {severidade}\n\nPor favor, tome as medidas necessárias."

        msg["Subject"] = "Alerta Crítico"
        msg["From"] = email_address
        msg["To"] = email

        msg.set_content(corpo_email)

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(email_address, token_senha)
            server.send_message(msg)

    def deletar_alerta(self, id_alerta: int) -> bool:
        return self.alertas_repository.deletar_alerta(id_alerta)

    def obter_contagem_por_tipo_epi(self) -> list[dict]:
        return self.alertas_repository.get_contagem_por_tipo_epi()

    def obter_contagem_por_dia(self, dias: int = 30) -> list[dict]:
        desde = datetime.now() - timedelta(days=dias)
        return self.alertas_repository.get_contagem_por_dia(desde)
