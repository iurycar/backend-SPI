from models.setores import Setor

class SetoresRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_setores(self) -> list[Setor] | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM setores")
            setores = cursor.fetchall()

            setores_lista: list[Setor] = []

            # Transfere todos os resultados para uma lista de objetos Setor
            if setores:
                for setor in setores:
                    setores_lista.append(Setor(
                        id=setor[0],
                        nome=setor[1]
                    ))

                return setores_lista
                
            return None

    def get_setor_por_id(self, setor_id: int) -> Setor | None:
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM setores WHERE id_setor = %s", (setor_id,))
            setor = cursor.fetchone()

            if setor:
                return Setor(
                    id=setor[0],
                    nome=setor[1]
                )

            return None

    def get_setores_por_id_responsavel(self, usuario_id: int) -> list[Setor] | None:
        with self.conn.cursor() as cursor:
            # Faz uma consulta para obter o setor associado ao usuário responsável
            # Usando join, une a tabela de setores com a tabela de responsabilidade para encontrar o setor do usuário
            cursor.execute(
                "SELECT s.id_setor, s.nome FROM setores s JOIN responsabilidade r ON s.id_setor = r.id_setor WHERE r.id_usuario = %s", (usuario_id,))
            setores = cursor.fetchall()

            setores_lista: list[Setor] = []

            if setores:
                for setor in setores:
                    setores_lista.append(Setor(
                        id=setor[0],
                        nome=setor[1]
                    ))

                return setores_lista

            return None

    def get_setor_por_id_zona(self, zona_id: int) -> Setor | None:
        with self.conn.cursor() as cursor:
            # Faz uma consulta para obter o setor associado à zona
            query = """SELECT s.id_setor, s.nome
                FROM setores s
                JOIN cameras c on c.id_setor = s.id_setor
                JOIN zonas z on z.id_camera = c.id_camera WHERE z.id_zona = %s"""
            
            cursor.execute(query, (zona_id,))
            setor = cursor.fetchone()

            if setor:
                return Setor(
                    id=setor[0],
                    nome=setor[1]
                )

            return None

    def get_responsaveis_por_setor(self, setor_id: int) -> list[int] | None:
        with self.conn.cursor() as cursor:
            # Faz uma consulta para obter os IDs dos usuários responsáveis pelo setor
            cursor.execute(
                "SELECT id_usuario FROM responsabilidade WHERE id_setor = %s", (setor_id,))
            responsaveis = cursor.fetchall()

            if responsaveis:
                return [responsavel[0] for responsavel in responsaveis]

            return None

    def get_setor_por_id_camera(self, camera_id: int) -> Setor | None:
        with self.conn.cursor() as cursor:
            # Faz uma consulta para obter o setor associado à câmera
            query = """SELECT s.id_setor, s.nome
                FROM setores s
                JOIN cameras c on c.id_setor = s.id_setor
                WHERE c.id_camera = %s"""
            
            cursor.execute(query, (camera_id,))
            setor = cursor.fetchone()

            if setor:
                return Setor(
                    id=setor[0],
                    nome=setor[1]
                )

            return None

    def registrar_setor(self, nome: str) -> Setor | None:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO setores (nome) VALUES (%s) RETURNING *",
                    (nome,)
                )
                self.conn.commit()
                setor = cursor.fetchone()

                if setor:
                    return Setor(
                        id=setor[0],
                        nome=setor[1]
                    )
            except Exception as e:
                print(f"Erro ao registrar setor: {e}")
                self.conn.rollback()
        return None

    def atualizar_setor(self, setor_id: int, nome: str) -> Setor | None:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "UPDATE setores SET nome = %s WHERE id_setor = %s RETURNING *",
                    (nome, setor_id)
                )
                self.conn.commit()
                setor = cursor.fetchone()

                if setor:
                    return Setor(
                        id=setor[0],
                        nome=setor[1]
                    )
            except Exception as e:
                print(f"Erro ao atualizar setor: {e}")
                self.conn.rollback()

        return None

    def deletar_setor(self, setor_id: int) -> bool:
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "DELETE FROM setores WHERE id_setor = %s",
                    (setor_id,)
                )
                self.conn.commit()
                return cursor.rowcount > 0
            
            except Exception as e:
                print(f"Erro ao deletar setor: {e}")
                self.conn.rollback()

        return False