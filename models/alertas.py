
class Alerta:
    def __init__(self, id: int, data: str, resolvido: bool = False):
        self.id = id
        self.data = data
        self.resolvido = resolvido