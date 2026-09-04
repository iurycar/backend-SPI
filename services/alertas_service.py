from repository.alertas_repository import AlertasRepository
from services.usuario_service import UsuarioService
from services.cameras_service import CamerasService
from services.setores_service import SetoresService

from models.cameras import Camera
from models.setores import Setor
from models.zonas import Zona

from extensions import socketio

from email.message import EmailMessage
import smtplib
import os

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

    def criar_alerta(self, monitoramento: Zona, id_usuario: int | None, evento: str, severidade: int = 1) -> bool:
        sucesso = self.alertas_repository.criar_alerta(monitoramento.id_monitorar, id_usuario, evento, severidade)

        if not sucesso:
            return False

        camera: Camera = self.cameras_service.obter_camera_por_id(monitoramento.id_camera)
        setor: Setor = self.setores_service.obter_setor_por_id(monitoramento.id_setor)

        payload_notificao = {
            'id_monitorar': monitoramento.id_monitorar,
            'id_camera': monitoramento.id_camera,
            'id_zona': monitoramento.id_zona,
            'id_usuario': id_usuario,
            'nome_zona': monitoramento.nome,
            'nome_camera': camera.nome if camera else None,
            'nome_setor': setor.nome if setor else None,
            'evento': evento,
            'severidade': severidade
        }

        socketio.emit('novo_alerta', payload_notificao, broadcast=True)

        if severidade == 3 and id_usuario:
            self._enviar_email_alerta_critico(id_usuario, monitoramento.nome, camera.nome, setor.nome, evento, severidade)

        return True

    def _enviar_email_alerta_critico(self, id_usuario: int, nome_zona: str, nome_camera: str, nome_setor: str, evento: str, severidade: int):
        email = self.usuario_service.obter_email_usuario_por_id(id_usuario)
        
        if email:

            email_address = os.getenv('EMAIL_ADDRESS')
            token_senha = os.getenv('EMAIL_PASSWORD')

            if email_address and token_senha:
                msg = EmailMessage()

                corpo_email = f"Alerta de severidade crítica, na zona de monitoramento:\n - Zona: {nome_zona if nome_zona else 'Não especificada'}\n - Câmera: {nome_camera}\n - Setor: {nome_setor}!\n\nEvento: {evento}\nSeveridade: {severidade}\n\nPor favor, tome as medidas necessárias."

                msg["Subject"] = "Alerta Crítico"
                msg["From"] = email_address
                msg["To"] = email

                msg.set_content(corpo_email)

                try:
                    with smtplib.SMTP('smtp.gmail.com', 587) as server:
                        server.starttls()
                        server.login(email_address, token_senha)
                        server.send_message(msg)

                except Exception as e:
                    print(f"Erro ao enviar email: {e}")

    def deletar_alerta(self, id_alerta: int) -> bool:
        return self.alertas_repository.deletar_alerta(id_alerta)