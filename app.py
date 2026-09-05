from dotenv import load_dotenv
from datetime import timedelta
from flask_cors import CORS
from flask_socketio import SocketIO
from flask import Flask
import multiprocessing as mp
import threading
import os

from controller.cameras_routes import create_cameras_bp
from controller.setores_routes import create_setores_bp
from controller.alertas_routes import create_alertas_bp
from controller.usuario_routes import create_user_bp
from controller.visao_routes import create_visao_bp
from controller.zonas_routes import create_zonas_bp
from controller.epi_routes import create_epi_bp


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
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
else:
    app.config['SESSION_COOKIE_HTTPONLY'] = True # Impede que o cookie seja acessado pelo JavaScript
    app.config['SESSION_COOKIE_SECURE'] = True # Garante que o cookie seja enviado apenas em conexões HTTPS
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Impede que o cookie seja enviado em solicitações de terceiros, mas permite em links normais

# Em desenvolvimento, aceita origens locais com credenciais. Em produção,
# configure explicitamente as origens permitidas no ambiente de implantação.
if DEV_INSECURE:
    CORS(app, supports_credentials=True, origins="*")
else:
    CORS(app, supports_credentials=True)

# SocketIO reaproveita a mesma política de origens da variável DEV_INSECURE já
# usada pelo CORS acima. async_mode='threading' funciona com o servidor de
# desenvolvimento do Werkzeug já usado por este projeto, sem exigir
# eventlet/gevent — decisão a revisitar se o projeto for para produção.
socketio = SocketIO(
    app,
    cors_allowed_origins="*" if DEV_INSECURE else None,
    async_mode='threading',
)

# Cria a classe conexão (agora um pool), para ser passada para os blueprints
conn = Connection()

# Fila usada pelos processos do VisionWorker (um por câmera) para repassar
# alertas recém-criados até o processo principal, onde o SocketIO de fato
# roda. Ver AlertasService.criar_alerta.
alertas_queue = mp.Queue()

def _relay_alertas_para_websocket():
    while True:
        alerta_dict = alertas_queue.get()
        socketio.emit('novo_alerta', alerta_dict)

threading.Thread(target=_relay_alertas_para_websocket, daemon=True).start()

app.register_blueprint(create_cameras_bp(conn))
app.register_blueprint(create_setores_bp(conn))
app.register_blueprint(create_alertas_bp(conn, alertas_queue=alertas_queue))
app.register_blueprint(create_zonas_bp(conn))
app.register_blueprint(create_visao_bp(conn, alertas_queue=alertas_queue))
app.register_blueprint(create_user_bp(conn))
app.register_blueprint(create_epi_bp(conn))


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
