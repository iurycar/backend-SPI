from models.zonas import Zona

class ZonasRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_zonas(self) -> list[Zona]:
        with self.conn.cursor() as cursor:
            query = """
                SELECT 
                    z.id_zona,
                    z.nome,
                    z.id_camera,
                    z.x,
                    z.y,
                    z.largura,
                    z.altura,
                    z.permitido,
                    COALESCE(
                        ARRAY_AGG(DISTINCT e.categoria) FILTER (WHERE e.categoria IS NOT NULL), 
                        '{}'
                    ) AS categorias_epis,
                    COALESCE(
                        ARRAY_AGG(DISTINCT e.id_epi) FILTER (WHERE e.id_epi IS NOT NULL), 
                        '{}'
                    ) AS ids_epis
                FROM zonas z
                LEFT JOIN monitorar m ON z.id_zona = m.id_zona
                LEFT JOIN epis e ON m.id_epi = e.id_epi
                GROUP BY z.id_zona
            """
            cursor.execute(query)
            zonas = cursor.fetchall()

            zonas_lista: list[Zona] = []

            if not zonas:
                return []

            # Transfere todos os resultados para uma lista de objetos Zona
            for zona in zonas:
                zonas_lista.append(Zona(
                    id=zona[0],
                    nome=zona[1],
                    id_camera=zona[2],
                    x=float(zona[3]),
                    y=float(zona[4]),
                    largura=float(zona[5]),
                    altura=float(zona[6]),
                    permitido=bool(zona[7]),
                    epis_categoria=list(zona[8]),
                    epis_id=list(zona[9])
                ))

            return zonas_lista

    def get_zona_por_id(self, zona_id: int) -> Zona | None:
        with self.conn.cursor() as cursor:
            query = """
                SELECT 
                    z.id_zona,
                    z.nome,
                    z.id_camera,
                    z.x,
                    z.y,
                    z.largura,
                    z.altura,
                    z.permitido,
                    COALESCE(
                        ARRAY_AGG(DISTINCT e.categoria) FILTER (WHERE e.categoria IS NOT NULL), 
                        '{}'
                    ) AS categorias_epis,
                    COALESCE(
                        ARRAY_AGG(DISTINCT e.id_epi) FILTER (WHERE e.id_epi IS NOT NULL), 
                        '{}'
                    ) AS ids_epis
                FROM zonas z
                LEFT JOIN monitorar m ON z.id_zona = m.id_zona
                LEFT JOIN epis e ON m.id_epi = e.id_epi
                WHERE z.id_zona = %s
                GROUP BY z.id_zona
            """
            cursor.execute(query, (zona_id,))
            zona = cursor.fetchone()

            if zona:
                return Zona(
                    id=zona[0],
                    nome=zona[1],
                    id_camera=zona[2],
                    x=float(zona[3]),
                    y=float(zona[4]),
                    largura=float(zona[5]),
                    altura=float(zona[6]),
                    permitido=bool(zona[7]),
                    epis_categoria=list(zona[8]),
                    epis_id=list(zona[9])
                )
            else:
                return None

    def get_zonas_por_id_camera(self, camera_id: int) -> list[Zona]:
        with self.conn.cursor() as cursor:
            query = """
                SELECT 
                    z.id_zona,
                    z.nome,
                    z.id_camera,
                    z.x,
                    z.y,
                    z.largura,
                    z.altura,
                    z.permitido,
                    COALESCE(
                        ARRAY_AGG(DISTINCT e.categoria) FILTER (WHERE e.categoria IS NOT NULL), 
                        '{}'
                    ) AS categorias_epis,
                    COALESCE(
                        ARRAY_AGG(DISTINCT e.id_epi) FILTER (WHERE e.id_epi IS NOT NULL), 
                        '{}'
                    ) AS ids_epis
                FROM zonas z
                LEFT JOIN monitorar m ON z.id_zona = m.id_zona
                LEFT JOIN epis e ON m.id_epi = e.id_epi
                WHERE z.id_camera = %s
                GROUP BY z.id_zona
            """
            cursor.execute(query, (camera_id,))
            zonas = cursor.fetchall()

            zonas_lista: list[Zona] = []

            # Transfere todos os resultados para uma lista de objetos Zona
            if zonas:
                for zona in zonas:
                    zonas_lista.append(Zona(
                        id=zona[0],
                        nome=zona[1],
                        id_camera=zona[2],
                        x=float(zona[3]),
                        y=float(zona[4]),
                        largura=float(zona[5]),
                        altura=float(zona[6]),
                        permitido=bool(zona[7]),
                        epis_categoria=list(zona[8]),
                        epis_id=list(zona[9])
                    ))

                return zonas_lista
            
            return []

    def get_id_camera_por_zona(self, zona_id: int) -> int | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id_camera FROM zonas WHERE id_zona = %s", (zona_id,))
            result = cursor.fetchone()

            if result:
                return result[0]
            else:
                return None

    def registrar_zona(self, 
                       nome: str | None, 
                       id_camera: int, 
                       x: float = 0.0, 
                       y: float = 0.0, 
                       largura: float = 1.0, 
                       altura: float = 1.0, 
                       permitido: bool = True, 
                       ids_epis: list[int] | None = None
    ) -> Zona | None:

        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    """
                    INSERT INTO zonas (nome, x, y, largura, altura, id_camera, permitido)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id_zona
                    """,
                    (nome, x, y, largura, altura, id_camera, permitido)
                )
                zona_criada = cursor.fetchone()
                if not zona_criada:
                    self.conn.rollback()
                    return None

                nova_zona_id = zona_criada[0]

                # Remove duplicatas se houver
                epis_unicos = list(set(ids_epis)) if ids_epis else []
                dados_monitorar: list[tuple[int, int | None]] = []

                if epis_unicos:
                    for id_epi in epis_unicos:
                        dados_monitorar.append((nova_zona_id, id_epi))

                    # Realiza a inserção em lote na tabela monitorar
                    cursor.executemany(
                        "INSERT INTO monitorar (id_zona, id_epi) VALUES (%s, %s)",
                        dados_monitorar
                    )
                else:
                    # Se não foi passado nenhum EPI (ex: zona proibida ou restrita sem EPI)
                    cursor.execute(
                        "INSERT INTO monitorar (id_zona, id_epi) VALUES (%s, NULL)",
                        (nova_zona_id,)
                    )

                self.conn.commit()

                # Reutiliza a busca para devolver o objeto Zona completo com as categorias de EPI
                return self.get_zona_por_id(nova_zona_id)
            
            except Exception as e:
                print(f"Erro ao registrar zona: {e}")
                self.conn.rollback()

        return None

    def atualizar_zona(self, 
                       zona_id: int, 
                       nome: str | None, 
                       id_camera: int, 
                       x: float = 0.0, 
                       y: float = 0.0, 
                       largura: float = 1.0, 
                       altura: float = 1.0, 
                       permitido: bool = True,
                       ids_epis: list[int] | None = None
        ) -> Zona | None:

        with self.conn.cursor() as cursor:
            try:
                # 1. Atualiza os dados básicos da zona
                cursor.execute(
                    """
                    UPDATE zonas 
                    SET nome = %s, x = %s, y = %s, largura = %s, altura = %s, id_camera = %s, permitido = %s 
                    WHERE id_zona = %s
                    """,
                    (nome, x, y, largura, altura, id_camera, permitido, zona_id)
                )

                if ids_epis is not None:
                    # 2. Obtém as regras atuais cadastradas em monitorar para esta zona
                    cursor.execute(
                        "SELECT id_epi, id_monitorar FROM monitorar WHERE id_zona = %s", 
                        (zona_id,)
                    )
                    linhas = cursor.fetchall()
                    
                    # Mapeia {id_epi: id_monitorar} (trata NULL como None para zonas restritas sem EPI)
                    mapa_atual = {linha[0]: linha[1] for linha in linhas}

                    # Define o conjunto de EPIs desejado
                    novos_epis = set(ids_epis) if ids_epis else {None}
                    epis_existentes = set(mapa_atual.keys())

                    # O que precisa entrar e o que precisa sair
                    epis_para_inserir = novos_epis - epis_existentes
                    epis_para_remover = epis_existentes - novos_epis

                    # Insere os novos vínculos
                    if epis_para_inserir:
                        dados_novos = [(zona_id, id_epi) for id_epi in epis_para_inserir]
                        cursor.executemany(
                            "INSERT INTO monitorar (id_zona, id_epi) VALUES (%s, %s)",
                            dados_novos
                        )

                    # Remove os vínculos descartados (apenas se não houver alerta vinculado)
                    if epis_para_remover:
                        ids_monitorar_remover = [mapa_atual[epi] for epi in epis_para_remover]
                        
                        # Verifica quais id_monitorar possuem alertas vinculados
                        cursor.execute(
                            "SELECT DISTINCT id_monitorar FROM alertas WHERE id_monitorar = ANY(%s)",
                            (ids_monitorar_remover,)
                        )
                        em_uso = {row[0] for row in cursor.fetchall()}

                        # Deleta com segurança apenas os que NÃO têm alertas
                        deletaveis = [m_id for m_id in ids_monitorar_remover if m_id not in em_uso]
                        if deletaveis:
                            cursor.execute(
                                "DELETE FROM monitorar WHERE id_monitorar = ANY(%s)",
                                (deletaveis,)
                            )

                self.conn.commit()
                return self.get_zona_por_id(zona_id)
            
            except Exception as e:
                print(f"Erro ao atualizar zona: {e}")
                self.conn.rollback()
                            
        return None

    def deletar_zona(self, zona_id: int) -> bool:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute("DELETE FROM zonas WHERE id_zona = %s", (zona_id,))
                self.conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"Erro ao deletar zona: {e}")
                self.conn.rollback()
                return False