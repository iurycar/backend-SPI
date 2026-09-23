from dataclasses import dataclass, field

@dataclass
class ZonaDTO:
    nome: str | None
    id_camera: int
    x: float = 0.0
    y: float = 0.0
    largura: float = 1.0
    altura: float = 1.0
    permitido: bool = True
    ids_epis: list[int] | None = field(default_factory=list)

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
        ids_epis = data.get('ids_epis', None)

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
        
        if ids_epis is not None:
            if not isinstance(ids_epis, list) or not all(isinstance(i, int) for i in ids_epis):
                raise ValueError("IDs dos EPIs must be a list of integers.")

        return cls(
            nome=nome,
            id_camera=id_camera,
            x=float(x),
            y=float(y),
            largura=float(largura),
            altura=float(altura),
            permitido=permitido,
            ids_epis=ids_epis
        )