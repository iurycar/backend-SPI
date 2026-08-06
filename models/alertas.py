
class Monitoramento:
    def __init__(self, 
                 id: int, 
                 id_camera: int, 
                 id_zona: int, 
                 id_epi: int,
                 data_hora: str,
                 resolvido: bool = False):
        self.id = id
        self.id_camera = id_camera
        self.id_zona = id_zona
        self.id_epi = id_epi
        self.data_hora = data_hora
        self.resolvido = resolvido