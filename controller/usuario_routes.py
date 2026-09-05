from flask import Blueprint, jsonify, request, session
from services.usuario_service import UsuarioService
import schemas.usuario_dto as usuario_dto
from core.errors import ValidationError

def create_user_bp(connection):
    user_bp = Blueprint('user_bp', __name__)
    usuario_service = UsuarioService(connection)

    @user_bp.route('/login', methods=['POST'])
    def login():
        data = request.get_json()

        try:    
            login_dto = usuario_dto.LoginDTO.from_dict(data)

            user = usuario_service.login(login_dto.email, login_dto.password)

            if user:
                session.permanent = True # Define a sessão como permanente para respeitar o tempo de expiração configurado
                session['user_id'] = user.id
                session['user_email'] = user.email
                session['user_perfil'] = user.perfil
                session['user_nome'] = user.nome
                session['user_sobrenome'] = user.sobrenome
                session['user_unidade'] = user.unidade
                session['user_telefone'] = user.telefone
                session['user_admin'] = user.is_admin()
                session['user_ativo'] = user.ativo
                session['user_acesso'] = str(user.acesso) if user.acesso else None

                # Retorna dados do usuário para o frontend armazenar localmente
                return jsonify({
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'nome': user.nome,
                        'sobrenome': user.sobrenome,
                        'email': user.email,
                        'perfil': user.perfil,
                        'unidade': user.unidade,
                        'telefone': user.telefone,
                        'admin': user.is_admin(),
                        'ativo': user.ativo
                    }
                }), 200
            else:
                return jsonify({'message': 'Invalid email or password'}), 401
            
        except ValidationError as e:
            return jsonify({'message': str(e)}), 400
        except Exception as e:
            print(f"Erro no login: {e}")
            return jsonify({'message': 'Erro interno do servidor'}), 500

    @user_bp.route('/logout', methods=['POST'])
    def logout():
        session.clear()
        return jsonify({'message': 'Logout successful'}), 200

    @user_bp.route('/session', methods=['GET'])
    def get_session():
        """
        Retorna os dados do usuário da sessão atual.
        Usado pelo frontend para validar se a sessão ainda está ativa
        e para recuperar o perfil do usuário após recarregamento da página.
        """
        if 'user_id' not in session:
            return jsonify({'message': 'Não autenticado'}), 401

        return jsonify({
            'authenticated': True,
            'user': {
                'id': session.get('user_id'),
                'nome': session.get('user_nome'),
                'sobrenome': session.get('user_sobrenome'),
                'email': session.get('user_email'),
                'perfil': session.get('user_perfil'),
                'unidade': session.get('user_unidade'),
                'telefone': session.get('user_telefone'),
                'admin': session.get('user_admin'),
                'ativo': session.get('user_ativo')
            }
        }), 200

    @user_bp.route('/signup', methods=['POST'])
    def signup():
        data = request.get_json()

        try:
            signup_dto = usuario_dto.SignupDTO.from_dict(data)
            user = usuario_service.signup(
                signup_dto.email, 
                signup_dto.password, 
                signup_dto.nome, 
                signup_dto.sobrenome, 
                signup_dto.perfil, 
                signup_dto.unidade, 
                signup_dto.telefone, 
            )

            if user:
                return jsonify({'message': 'Signup successful'}), 201
            else:
                return jsonify({'message': 'Email already exists'}), 400

        except ValidationError as e:
            return jsonify({'message': str(e)}), 400
        except Exception as e:
            print(f"Erro no signup: {e}")
            return jsonify({'message': 'Erro interno do servidor'}), 500

    return user_bp