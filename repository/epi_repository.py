
class EpiRepository:
    def __init__(self, connection):
        self.conn = connection

    def get_epis(self) -> list:

        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM epis")
            epis = cursor.fetchall()

            return epis