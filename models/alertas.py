from dataclasses import dataclass

@dataclass
class Alerta:
    id: int
    id_zona: int
    id_monitorar: int
    id_epi: int | None
    id_usuario: int | None
    data: str
    resolvido: bool = False
    evento: str = ""