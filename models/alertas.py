from dataclasses import dataclass

@dataclass
class Alerta:
    id: int
    data: str
    resolvido: bool = False