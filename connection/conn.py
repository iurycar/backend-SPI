import load_dotenv
import psycopg2
import os

load_dotenv()

host = os.getenv('DB_HOST')
port = os.getenv('DB_PORT')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
database = os.getenv('DB_NAME')

def get_connection() -> psycopg2.extensions.connection | None:
    try:
        with psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=database
        ) as conn:
            print("Conexão com o banco de dados estabelecida com sucesso.")
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

    return conn