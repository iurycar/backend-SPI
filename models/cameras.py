from dataclasses import dataclass

@dataclass
class Camera:
    id: int
    nome: str | None
    ip: str
    id_setor: int