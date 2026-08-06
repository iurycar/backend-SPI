
class Zona:
    def __init__(self, 
                 id: int, 
                 nome: str, 
                 id_camera: int, 
                 x1: int = 0, 
                 y1: int = 0, 
                 x2: int = 1920, 
                 y2: int = 1080):
        self.id = id
        self.nome = nome
        self.id_camera = id_camera
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2