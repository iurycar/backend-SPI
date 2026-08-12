from load_dotenv import load_dotenv
import psycopg2
import os

load_dotenv()

host = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
database = os.getenv('DB_NAME')

class Connection:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )

    def get_connection(self):
        print(f"Conexão com o banco de dados estabelecida: {self.conn}")
        return self.conn