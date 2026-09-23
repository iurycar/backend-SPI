from repository.monitoramento_repository import MonitoramentoRepository
from repository.alertas_repository import AlertasRepository
from services.usuario_service import UsuarioService
from services.cameras_service import CamerasService
from services.setores_service import SetoresService

from extensions import emitir_evento_setor, emitir_evento_global

from datetime import datetime, timedelta

from models.zonas import Zona

from core.tipo_deteccao import TIPOS_POSTURA, validar_vinculo_alerta

from tasks.email_task import task_enviar_email_alerta_critico
from extensions import redis_client, emitir_evento_global
from tasks.alarme_task import enviar_comando
from rq import Queue

email_queue = Queue('emails', connection=redis_client)  # Cria uma fila de tarefas para envio de e-mails

class AlertasService:
    def __init__(self, connection):
        self.connection = connection
        self.monitoramento_repository = MonitoramentoRepository(connection)
        self.alertas_repository = AlertasRepository(connection)
        self.usuario_service = UsuarioService(connection)
        self.cameras_service = CamerasService(connection)
        self.setores_service = SetoresService(connection)

    @staticmethod
    def _serializar_alerta(alerta) -> dict:
        return {
            'id': alerta.id,
            'resolvido': alerta.resolvido,
            'data': alerta.data_hora,
            'id_monitorar': alerta.id_monitorar,
            'id_usuario': alerta.id_usuario,
            'evento': alerta.evento,
            'severidade': alerta.severidade,
            'id_zona': alerta.id_zona,
            'id_camera': alerta.id_camera,
            'id_epi': alerta.id_epi,
            'tipo_deteccao': alerta.tipo_deteccao,
        }

    def obter_alertas(self, tipo: str | None = None) -> list[dict]:
        return [self._serializar_alerta(a) for a in self.alertas_repository.get_alertas(tipo)]

    def obter_alertas_por_id_camera(self, camera_id: int, tipo: str | None = None) -> list[dict]:
        return [self._serializar_alerta(a)
                for a in self.alertas_repository.get_alertas_por_id_camera(camera_id, tipo)]

    def obter_alertas_por_id_zona(self, zona_id: int, tipo: str | None = None) -> list[dict]:
        return [self._serializar_alerta(a)
                for a in self.alertas_repository.get_alertas_por_id_zona(zona_id, tipo)]

    def obter_alerta_por_id(self, alerta_id: int) -> dict | None:
        alerta = self.alertas_repository.get_alerta_por_id(alerta_id)
        return self._serializar_alerta(alerta) if alerta else None

    def marcar_alerta_resolvido(self, id_alerta: int) -> bool:
        sucesso = self.alertas_repository.marcar_alerta_resolvido(id_alerta)
        if not sucesso:
            return False

        # Desligar remotamente o alarme associado ao alerta, se houver
        monitoramento = self.alertas_repository.get_monitoramento_por_id_alerta(id_alerta)
        if not monitoramento:
            return True
        alarme = self.monitoramento_repository.get_alarme_por_id_monitorar(monitoramento['id_monitorar'])

        if alarme:
            enviar_comando(comando="RESET", endereco_esp32=alarme['endereco'])

        return sucesso

    def registrar_alertas_com_notificacao_unica(self, 
                                                monitoramento: Zona | dict,
                                                responsaveis: list[int] | None, 
                                                evento: str,
                                                severidade: int = 1, 
                                                *, 
                                                tipo_deteccao: str = 'epi') -> bool:
        id_monitorar = self._campo_monitoramento(monitoramento, 'id_monitorar')
        validar_vinculo_alerta(tipo_deteccao, id_monitorar, None)
        usuarios_registrados = []
        
        lista_responsaveis = responsaveis if responsaveis else [None]

        for responsavel_id in lista_responsaveis:
            sucesso = self.alertas_repository.criar_alerta(
                id_monitorar, responsavel_id, evento, severidade, tipo_deteccao=tipo_deteccao
            )
            if sucesso:
                usuarios_registrados.append(responsavel_id)
                if severidade == 3 and responsavel_id is not None:
                    self._enviar_email_alerta_critico(
                        responsavel_id, self._campo_monitoramento(monitoramento, 'nome'),
                        '', '', evento, severidade
                    )

        if not usuarios_registrados:
            return False

        payload_notificacao = self._montar_payload_alerta(
            monitoramento, usuarios_registrados[0], evento, severidade, tipo_deteccao=tipo_deteccao
        )

        if severidade == 3:
            emitir_evento_global('novo_alerta', payload_notificacao)
        else:
            id_zona = self._campo_monitoramento(monitoramento, 'id') or self._campo_monitoramento(monitoramento, 'id_zona')
            setor = self.setores_service.obter_setor_por_id_zona(id_zona)
            if setor:
                id_setor = setor.get('id') if isinstance(setor, dict) else getattr(setor, 'id', None)
                if id_setor:
                    emitir_evento_setor('novo_alerta', payload_notificacao, id_setor=id_setor)

        return True

    def criar_alerta(self, 
                     monitoramento: Zona | dict | None,
                     id_usuario: int | None, 
                     evento: str, severidade: int = 1, 
                     destinatarios: list[int] | None = None, *,
                     tipo_deteccao: str = 'epi', id_camera: int | None = None
        ) -> bool:
        
        id_monitorar = self._campo_monitoramento(monitoramento, 'id_monitorar')

        validar_vinculo_alerta(tipo_deteccao, id_monitorar, id_camera)

        if tipo_deteccao in TIPOS_POSTURA and monitoramento is not None:
            raise ValueError('Postura não aceita contexto de zona ou monitoramento.')

        payload_notificacao = self._montar_payload_alerta(
            monitoramento, id_usuario, evento, severidade,
            tipo_deteccao=tipo_deteccao, id_camera=id_camera
        )

        sucesso = self.alertas_repository.criar_alerta(
            id_monitorar, id_usuario, evento, severidade,
            tipo_deteccao=tipo_deteccao, id_camera=id_camera
        )

        if not sucesso:
            return False
        
        # Dispara e-mail para todos os responsáveis se for severidade 3
        if severidade == 3:
            emitir_evento_global('novo_alerta', payload_notificacao)

            lista_envio = destinatarios or ([id_usuario] if id_usuario else [])
            for usuario_id in lista_envio:
                self._enviar_email_alerta_critico(
                    usuario_id, payload_notificacao['nome_zona'],
                    payload_notificacao['nome_camera'], payload_notificacao['nome_setor'],
                    evento, severidade
                )
        else:
            id_setor = None
            if id_camera is not None:
                camera = self.cameras_service.obter_camera_por_id(id_camera)
    
                if camera:
                    id_setor = camera.get('id_setor')
    
            elif monitoramento is not None:
                id_zona = self._campo_monitoramento(monitoramento, 'id') or self._campo_monitoramento(monitoramento, 'id_zona')
                setor = self.setores_service.obter_setor_por_id_zona(id_zona)
    
                if setor:
                    id_setor = setor.get('id')
    
            if id_setor is not None:
                emitir_evento_setor('novo_alerta', payload_notificacao, id_setor=id_setor)

        return True

    @staticmethod
    def _campo_monitoramento(monitoramento: Zona | dict | None, campo: str):
        if isinstance(monitoramento, dict):
            return monitoramento.get(campo)
        
        return getattr(monitoramento, campo, None)

    def _montar_payload_alerta(self, monitoramento: Zona | dict | None, id_usuario: int | None,
                             evento: str, severidade: int, *, tipo_deteccao: str = 'epi',
                             id_camera: int | None = None) -> dict:
        id_camera = id_camera if id_camera is not None else self._campo_monitoramento(monitoramento, 'id_camera')
        id_zona = (self._campo_monitoramento(monitoramento, 'id')
                   or self._campo_monitoramento(monitoramento, 'id_zona'))
        camera = self.cameras_service.obter_camera_por_id(id_camera)
        if tipo_deteccao in TIPOS_POSTURA:
            if not camera:
                raise ValueError('Câmera não encontrada para registrar postura.')
            setor = self.setores_service.obter_setor_por_id(camera['id_setor'])
        else:
            setor = self.setores_service.obter_setor_por_id_zona(id_zona)
        return {
            'id_monitorar': self._campo_monitoramento(monitoramento, 'id_monitorar'),
            'id_camera': id_camera,
            'id_zona': id_zona,
            'id_usuario': id_usuario,
            'nome_zona': self._campo_monitoramento(monitoramento, 'nome'),
            'nome_camera': camera.get('nome') if camera else None,
            'nome_setor': setor.get('nome') if setor else None,
            'evento': evento,
            'severidade': severidade,
            'tipo_deteccao': tipo_deteccao,
        }

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

    def obter_contagem_por_tipo_epi(self) -> list[dict]:
        return self.alertas_repository.get_contagem_por_tipo_epi()

    def obter_contagem_por_periodo(self, dias: int = 30) -> list[dict]:
        desde = datetime.now() - timedelta(days=dias)
        return self.alertas_repository.get_contagem_por_periodo(desde)
