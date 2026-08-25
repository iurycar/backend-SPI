from dataclasses import dataclass

@dataclass
class ZonaDTO:
    nome: str | None
    id_camera: int
    x: int = 0
    y: int = 0
    largura: int = 1920
    altura: int = 1080
    permitido: bool = True
    id_epi: int | None = None

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
        permitido = data.get('permitido', True)
        id_epi = data.get('id_epi', None)

        if nome is not None and not isinstance(nome, str):
            raise ValueError("Nome must be a string or None.")
        if not isinstance(id_camera, int):
            raise ValueError("ID da câmera must be an integer.")
        if not isinstance(x, int) or not isinstance(y, int) or not isinstance(largura, int) or not isinstance(altura, int):
            raise ValueError("Coordinates must be integers.")
        if not isinstance(largura, int) or not isinstance(altura, int):
            raise ValueError("Width and height must be integers.")
        if not isinstance(permitido, bool):
            raise ValueError("Permitido must be a boolean.")
        if not isinstance(id_epi, int) and id_epi is not None:
            raise ValueError("ID do EPI must be an integer or None.")

        return cls(
            nome=nome,
            id_camera=id_camera,
            x=x,
            y=y,
            largura=largura,
            altura=altura,
            permitido=permitido,
            id_epi=id_epi
        )