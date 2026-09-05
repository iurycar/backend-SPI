from dataclasses import dataclass

@dataclass
class Zona:
    id: int
    nome: str | None
    id_camera: int
    x: float = 0.0
    y: float = 0.0
    largura: float = 1.0
    altura: float = 1.0
    permitido: bool = True
    epis_categoria: list[str] | None = None
    regiao: list[tuple[int, int]] | None = None
    id_monitorar: int | None = None