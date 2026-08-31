from repository.alertas_repository import AlertasRepository

class AlertasService:
    def __init__(self, connection):
        self.connection = connection
        self.alertas_repository = AlertasRepository(connection)

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
        return self.alertas_repository.criar_alerta(id_monitorar, id_usuario, evento, severidade)

    def deletar_alerta(self, id_alerta: int) -> bool:
        return self.alertas_repository.deletar_alerta(id_alerta)