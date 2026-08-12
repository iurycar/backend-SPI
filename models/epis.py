from dataclasses import dataclass

@dataclass
class EPI:
    id: int
    nome: str
    categoria: str
    certificado: str
    validade: str
    estoque: int