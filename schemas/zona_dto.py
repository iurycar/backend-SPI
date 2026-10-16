from dataclasses import dataclass, field

@dataclass
class ZonaDTO:
    nome: str | None
    id_camera: int
    poligono: list[list[float]]
    permitido: bool = True
    ids_epis: list[int] | None = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Payload invalid.")

        nome = data.get('nome')
        id_camera = data.get('id_camera')
        poligono = data.get('poligono')
        permitido = data.get('permitido', True)
        ids_epis = data.get('ids_epis', None)

        if nome is not None and not isinstance(nome, str):
            raise ValueError("Nome must be a string or None.")
        
        if not isinstance(id_camera, int):
            raise ValueError("ID da câmera must be an integer.")
        
        if not isinstance(poligono, list):
            raise ValueError("Polígono must be a list.")
        
        if not all(isinstance(ponto, list) and len(ponto) == 2 and all(isinstance(coord, (int, float)) for coord in ponto) for ponto in poligono):
            raise ValueError("Polígono must be a list of lists with two float coordinates each.")
        
        if not isinstance(permitido, bool):
            raise ValueError("Permitido must be a boolean.")
        
        if ids_epis is not None:
            if not isinstance(ids_epis, list) or not all(isinstance(i, int) for i in ids_epis):
                raise ValueError("IDs dos EPIs must be a list of integers.")

        return cls(
            nome=nome,
            id_camera=id_camera,
            poligono=poligono,
            permitido=permitido,
            ids_epis=ids_epis
        )