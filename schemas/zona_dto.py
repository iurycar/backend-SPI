from dataclasses import dataclass

@dataclass
class ZonaDTO:
    nome: str | None
    id_camera: int
    x1: int = 0
    y1: int = 0
    x2: int = 1920
    y2: int = 1080

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Payload invalid.")

        nome = data.get('nome')
        id_camera = data.get('id_camera')
        x1 = data.get('x1', 0)
        y1 = data.get('y1', 0)
        x2 = data.get('x2', 1920)
        y2 = data.get('y2', 1080)

        if nome is not None and not isinstance(nome, str):
            raise ValueError("Nome must be a string or None.")
        if not isinstance(id_camera, int):
            raise ValueError("ID da câmera must be an integer.")
        if not isinstance(x1, int) or not isinstance(y1, int) or not isinstance(x2, int) or not isinstance(y2, int):
            raise ValueError("Coordinates must be integers.")

        return cls(
            nome=nome,
            id_camera=id_camera,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2
        )