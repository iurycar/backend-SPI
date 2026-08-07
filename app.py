from flask import Flask, request, jsonify, Blueprint, session
from dotenv import load_dotenv
from datetime import timedelta
from flask_cors import CORS
import os

from controller.epi_routes import epi_bp
from controller.usuario_routes import user_bp

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# Configurações de segurança para a sessão
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_HTTPONLY'] = True # Impede que o cookie seja acessado pelo JavaScript
app.config['SESSION_COOKIE_SECURE'] = True # Garante que o cookie seja enviado apenas em conexões HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Impede que o cookie seja enviado em solicitações de terceiros, mas permite em links normais

# Habilita CORS para permitir solicitações de diferentes origens, incluindo credenciais (cookies)
CORS(app, supports_credentials=True)

app.register_blueprint(epi_bp)
app.register_blueprint(user_bp)

if __name__ == '__main__':
    app.run(debug=True)