from dataclasses import dataclass, field

@dataclass
class Zona:
    id: int
    nome: str | None
    id_camera: int
    poligono: list[list[float]]
    permitido: bool = True
    epis_categoria: list[str] = field(default_factory=list)
    epis_id: list[int] = field(default_factory=list)
    id_monitorar: list[int] | None = None
    regiao: list[tuple[int, int]] | None = None