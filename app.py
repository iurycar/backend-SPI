from dotenv import load_dotenv
from datetime import timedelta
from flask_cors import CORS
from flask import Flask
import os

from controller.cameras_routes import create_cameras_bp
from controller.setores_routes import create_setores_bp
from controller.usuario_routes import create_user_bp
from controller.visao_routes import create_visao_bp
from controller.zonas_routes import create_zonas_bp
from controller.epi_routes import create_epi_bp
from controller.visao_routes import visao_bp


from connection.conn import Connection

load_dotenv()  # Carrega as variáveis de ambiente do arquivo .env

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

DEV_INSECURE = os.getenv('DEV_INSECURE', 'false').lower() == 'true'

# Configurações de segurança para a sessão
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

print(f"DEV_INSECURE: {DEV_INSECURE}")

# Configurações de cookies de sessão com base na variável DEV_INSECURE
if DEV_INSECURE:
    app.config['SESSION_COOKIE_HTTPONLY'] = False  # Permite que o cookie seja acessado pelo JavaScript
    app.config['SESSION_COOKIE_SECURE'] = False  # Permite que o cookie seja enviado em conexões HTTP
    app.config['SESSION_COOKIE_SAMESITE'] = None  # Permite que o cookie seja enviado em solicitações de terceiros
else:
    app.config['SESSION_COOKIE_HTTPONLY'] = True # Impede que o cookie seja acessado pelo JavaScript
    app.config['SESSION_COOKIE_SECURE'] = True # Garante que o cookie seja enviado apenas em conexões HTTPS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Impede que o cookie seja enviado em solicitações de terceiros, mas permite em links normais

# Habilita CORS para permitir solicitações de diferentes origens, incluindo credenciais (cookies)
CORS(app, supports_credentials=True)

# Cria a classe conexão, para ser passada para os blueprints
conn = Connection()

app.register_blueprint(create_cameras_bp(conn.get_connection()))
app.register_blueprint(create_setores_bp(conn.get_connection()))
app.register_blueprint(create_zonas_bp(conn.get_connection()))
app.register_blueprint(create_visao_bp(conn.get_connection()))
app.register_blueprint(create_user_bp(conn.get_connection()))
app.register_blueprint(create_epi_bp(conn.get_connection()))


if __name__ == '__main__':
    app.run(debug=True)