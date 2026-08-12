from dataclasses import dataclass

@dataclass
class Zona:
    id: int
    nome: str
    id_camera: int
    x1: int = 0
    y1: int = 0
    x2: int = 1920
    y2: int = 1080