from flask import Blueprint, jsonify, request, session
from services.usuario_service import UsuarioService

def create_user_bp(connection):
    user_bp = Blueprint('user_bp', __name__)
    service = UsuarioService(connection)

    @user_bp.route('/login', methods=['POST'])
    def login():
        data = request.get_json()

        user_email = data.get('email')
        user_password = data.get('password')

        user = service.login(user_email, user_password)

        print(f"Dados recebidos: {data}")

        if user:
            session['user_id'] = user.id
            return jsonify({'message': 'Login successful'}), 200
        else:
            return jsonify({'message': 'Invalid email or password'}), 401


    @user_bp.route('/logout', methods=['POST'])
    def logout():
        session.pop('user_id', None)
        return jsonify({'message': 'Logout successful'}), 200


    @user_bp.route('/signup', methods=['POST'])
    def signup():
        data = request.get_json()

        user_email = data.get('email')
        user_password = data.get('password')

        user = service.signup(user_email, user_password)

        if user:
            return jsonify({'message': 'Signup successful'}), 201
        else:
            return jsonify({'message': 'Email already exists'}), 400

    return user_bp