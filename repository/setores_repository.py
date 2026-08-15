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