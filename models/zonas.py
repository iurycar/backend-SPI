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
    permitido: bool = True
    epis_categoria: list[str] | None = None
    regiao: list[tuple[int, int]] | None = None
    id_monitorar: int | None = None