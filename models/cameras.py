from dataclasses import dataclass

@dataclass
class Camera:
    id: int
    nome: str | None
    ip: str
    id_setor: int
    rotacao: int = 0
    espelhar_horizontal: bool = False
    espelhar_vertical: bool = False