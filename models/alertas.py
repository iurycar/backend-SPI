from dataclasses import dataclass

@dataclass
class Alerta:
    id: int
    id_zona: int | None
    id_monitorar: int | None
    id_epi: int | None
    id_usuario: int | None
    id_camera: int | None
    data_hora: str
    resolvido: bool = False
    evento: str = ""
    severidade: int = 1
    tipo_deteccao: str = 'epi'
