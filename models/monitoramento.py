from dataclasses import dataclass

@dataclass
class Monitoramento:
    id: int
    id_zona: int
    id_epi: int | None = None