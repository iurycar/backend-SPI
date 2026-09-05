from dataclasses import dataclass

@dataclass
class ZonaDTO:
    nome: str | None
    id_camera: int
    x: float = 0.0
    y: float = 0.0
    largura: float = 1.0
    altura: float = 1.0
    permitido: bool = True
    id_epi: int | None = None

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Payload invalid.")

        nome = data.get('nome')
        id_camera = data.get('id_camera')
        x = data.get('x', 0.0)
        y = data.get('y', 0.0)
        largura = data.get('largura', 1.0)
        altura = data.get('altura', 1.0)
        permitido = data.get('permitido', True)
        id_epi = data.get('id_epi', None)

        if nome is not None and not isinstance(nome, str):
            raise ValueError("Nome must be a string or None.")
        if not isinstance(id_camera, int):
            raise ValueError("ID da câmera must be an integer.")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError("Coordinates x and y must be numbers.")
        if not isinstance(largura, (int, float)) or not isinstance(altura, (int, float)):
            raise ValueError("Width and height must be numbers.")
        if not isinstance(permitido, bool):
            raise ValueError("Permitido must be a boolean.")
        if not isinstance(id_epi, int) and id_epi is not None:
            raise ValueError("ID do EPI must be an integer or None.")

        return cls(
            nome=nome,
            id_camera=id_camera,
            x=float(x),
            y=float(y),
            largura=float(largura),
            altura=float(altura),
            permitido=permitido,
            id_epi=id_epi
        )