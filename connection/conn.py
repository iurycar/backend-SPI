from contextlib import contextmanager
from dotenv import load_dotenv
from psycopg2 import pool
import os

load_dotenv()

host = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
database = os.getenv('DB_NAME')

class Connection:
    def __init__(self):
        min_conn = int(os.getenv('DB_POOL_MIN_CONN', 1))
        max_conn = int(os.getenv('DB_POOL_MAX_CONN', 10))

        self.pool = pool.ThreadedConnectionPool(
            min_conn,
            max_conn,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )

    @contextmanager
    def get_connection(self):
        """Empresta uma conexão do pool e a devolve ao final do bloco `with`.

        Em caso de exceção, faz rollback na própria conexão antes de
        devolvê-la ao pool, para nunca devolver uma transação abortada.
        """
        connection = self.pool.getconn()

        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        finally:
            self.pool.putconn(connection)
