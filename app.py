from flask_session import Session
from dotenv import load_dotenv
from datetime import timedelta
from flask_cors import CORS
from flask import Flask
import atexit
import redis
import os

from extensions import socketio, REDIS_URL
from events.alertas_events import register_socket_events
from worker.vision_manager import iniciar_vision_workers, parar_vision_workers
from connection.conn import Connection

from controller.cameras_routes import create_cameras_bp
from controller.setores_routes import create_setores_bp
from controller.alertas_routes import create_alertas_bp
from controller.usuario_routes import create_user_bp
from controller.visao_routes import create_visao_bp
from controller.zonas_routes import create_zonas_bp
from controller.epi_routes import create_epi_bp

load_dotenv()  # Carrega as variáveis de ambiente do arquivo .env

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configuração da Sessão no Redis
app.config['SESSION_TYPE'] = 'redis' # Configura o tipo de sessão para usar Redis
app.config['SESSION_PERMANENT'] = True # Define a sessão como permanente
app.config['SESSION_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_USE_SIGNER'] = True # Habilita a assinatura do cookie de sessão para maior segurança
app.config['SESSION_REDIS'] = redis.Redis.from_url(REDIS_URL) # Define a URL do Redis para armazen

Session(app)  # Inicializa a sessão do Flask

socketio.init_app(app, cors_allowed_origins="*")  # Inicializa o SocketIO com o aplicativo Flask
register_socket_events(socketio)  # Registra os eventos do WebSocket

DEV_INSECURE = os.getenv('DEV_INSECURE', 'false', message_queue=REDIS_URL).lower() == 'true'

# Configurações de segurança para a sessão
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

print(f"DEV_INSECURE: {DEV_INSECURE}")

# Configurações de cookies de sessão com base na variável DEV_INSECURE
if DEV_INSECURE:
    app.config['SESSION_COOKIE_HTTPONLY'] = False  # Permite que o cookie seja acessado pelo JavaScript
    app.config['SESSION_COOKIE_SECURE'] = False  # Permite que o cookie seja enviado em conexões HTTP
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
else:
    app.config['SESSION_COOKIE_HTTPONLY'] = True # Impede que o cookie seja acessado pelo JavaScript
    app.config['SESSION_COOKIE_SECURE'] = True # Garante que o cookie seja enviado apenas em conexões HTTPS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Em desenvolvimento, aceita origens locais com credenciais. Em produção,
# configure explicitamente as origens permitidas no ambiente de implantação.
if DEV_INSECURE:
    CORS(app, supports_credentials=True, origins="*")
else:
    CORS(app, supports_credentials=True)

# Cria a classe conexão, para ser passada para os blueprints
conn = Connection()

app.register_blueprint(create_cameras_bp(conn.get_connection()))
app.register_blueprint(create_setores_bp(conn.get_connection()))
app.register_blueprint(create_alertas_bp(conn.get_connection()))
app.register_blueprint(create_zonas_bp(conn.get_connection()))
app.register_blueprint(create_visao_bp(conn.get_connection()))
app.register_blueprint(create_user_bp(conn.get_connection()))
app.register_blueprint(create_epi_bp(conn.get_connection()))


if __name__ == '__main__':
    atexit.register(parar_vision_workers)  # Registra a função para parar os workers ao encerrar o servidor

    # Evita que o reloader do Flask (debug=True) inicie os workers 2 vezes no OpenCV
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        iniciar_vision_workers([1])

    socketio.run(host='0.0.0.0', port=5000, debug=True)
