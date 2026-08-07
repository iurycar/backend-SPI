from flask import Blueprint, jsonify, request, session
from services.usuario_service import UsuarioService
from repository.usuario_repository import UsuarioRepository

user_bp = Blueprint('user_bp', __name__)

@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    user_email = data.get('email')
    user_password = data.get('password')

    repo = UsuarioRepository()
    service = UsuarioService(repo)

    user = service.login(user_email, user_password)

    print(f"Dados recebidos: {data}")

    if user:
        session['user_id'] = user.id
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid email or password'}), 401