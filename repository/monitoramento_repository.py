from models.zonas import Zona

class MonitoramentoRepository:
    def __init__(self, connection):
        self.connection = connection

    def get_zonas_monitoradas_por_id_camera(self, camera_id) -> list[Zona]:
        """
        Retorna uma lista de objetos Zona para uma câmera específica.
        """
        with self.connection.cursor() as cursor:
            # Uso do LEFT JOIN para garantir que zonas sem EPIs (proibidas) também sejam retornadas
            query = """
                SELECT m.id_monitorar, z.id_camera, m.id_zona, m.id_epi, z.nome, z.x, z.y, z.largura, z.altura, z.permitido, e.categoria
                FROM zonas z
                JOIN monitorar m ON z.id_zona = m.id_zona
                LEFT JOIN epis e ON m.id_epi = e.id_epi
                WHERE z.id_camera = %s
            """

            cursor.execute(query, (camera_id,))
            consulta = cursor.fetchall()

            if not consulta:
                return [] # Retornar lista vazia em vez de None evita erro de iteração no service

            zonas: list[Zona] = []

            for monitorar in consulta:
                zona_id = monitorar[2]
                categoria_epi = monitorar[10]
                permitido = bool(monitorar[9])

                zona_existente = next((z for z in zonas if z.id == zona_id), None)

                if zona_existente:
                    if categoria_epi and categoria_epi not in zona_existente.epis_categoria:
                        zona_existente.epis_categoria.append(categoria_epi)

                else:
                    x = float(monitorar[5])
                    y = float(monitorar[6])
                    largura = float(monitorar[7])
                    altura = float(monitorar[8])

                    regiao = [
                        (x, y),
                        (x + largura, y),
                        (x + largura, y + altura),
                        (x, y + altura)
                    ]

                    # Adiciona a categoria apenas se ela existir (não for None)
                    epis = [categoria_epi] if categoria_epi else []

                    zona = Zona(
                        id=zona_id,
                        nome=monitorar[4],
                        id_camera=monitorar[1],
                        id_monitorar=monitorar[0],
                        x=x,
                        y=y,
                        largura=largura,
                        altura=altura,
                        permitido=permitido,
                        epis_categoria=epis,
                        regiao=regiao
                    )
                        
                    zonas.append(zona)

            return zonas

    def get_alarme_por_id_monitorar(self, id_monitorar: int) -> dict | None:
            with self.conn.cursor() as cursor:
                query = "SELECT a.id_alarme, a.endereco, a.id_monitorar FROM alarmes a WHERE a.id_monitorar = %s;"
                cursor.execute(query, (id_monitorar,))
                alarme = cursor.fetchone()
    
                if alarme:
                    return {
                        "id_alarme": alarme[0],
                        "endereco": alarme[1],
                        "id_monitorar": alarme[2]
                    }
                else:
                    return None