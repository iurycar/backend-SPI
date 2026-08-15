from dataclasses import dataclass

@dataclass
class SetorDTO:
    nome: str

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Payload invalid.")

        nome = data.get('nome')

        if not isinstance(nome, str):
            raise ValueError("Nome must be a string.")

        return cls(
            id=id,
            nome=nome
        )