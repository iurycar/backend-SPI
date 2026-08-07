from flask import Flask, request, jsonify, Blueprint, session
from datetime import timedelta
from flask_cors import CORS
import os

from controller.epi_routes import epi_bp
from controller.usuario_routes import user_bp

app = Flask(__name__)
app.secret_key = os.getenv('secret_key')

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

app.register_blueprint(epi_bp)
app.register_blueprint(user_bp)

if __name__ == '__main__':
    app.run(debug=True)