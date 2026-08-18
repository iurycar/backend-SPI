from dataclasses import dataclass

@dataclass
class Zona:
    id: int
    nome: str | None
    id_camera: int
    x: int = 0
    y: int = 0
    largura: int = 1920
    altura: int = 1080