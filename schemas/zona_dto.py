from dataclasses import dataclass

@dataclass
class ZonaDTO:
    nome: str | None
    id_camera: int
    x: int = 0
    y: int = 0
    largura: int = 1920
    altura: int = 1080

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Payload invalid.")

        nome = data.get('nome')
        id_camera = data.get('id_camera')
        x = data.get('x', 0)
        y = data.get('y', 0)
        largura = data.get('largura', 1920)
        altura = data.get('altura', 1080)

        if nome is not None and not isinstance(nome, str):
            raise ValueError("Nome must be a string or None.")
        if not isinstance(id_camera, int):
            raise ValueError("ID da câmera must be an integer.")
        if not isinstance(x, int) or not isinstance(y, int) or not isinstance(largura, int) or not isinstance(altura, int):
            raise ValueError("Coordinates must be integers.")

        return cls(
            nome=nome,
            id_camera=id_camera,
            x=x,
            y=y,
            largura=largura,
            altura=altura
        )