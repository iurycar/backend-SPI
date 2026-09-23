from flask import jsonify, session
from functools import wraps

""" Módulo para verificar se há autenticação e autorização para rotas Flask. """

def login_required(view):
    """ Decorator para verificar se o usuário está autenticado e ativo antes de acessar a rota. """
    @wraps(view)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'message': 'Não autenticado'}), 401

        if session.get('user_ativo') is False:
            return jsonify({'message': 'Usuário inativo'}), 403
        
        return view(*args, **kwargs)

    return decorated_function

def perfil_required(*perfis_permitidos):
    """ 
        Decorator para verificar se o usuário possui privilégios necessários antes de acessar a rota. 
        Exemplos de uso:
            @perfil_required('admin', 'operador')
            @perfil_required('admin')
    """
    def decorator(view):
        @wraps(view)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'message': 'Não autenticado'}), 401

            if session.get('user_ativo') is False:
                return jsonify({'message': 'Usuário inativo'}), 403

            perfis_validos = []
            for perfil in perfis_permitidos:
                perfis_validos.append(perfil.strip().lower())

            user_perfil = session.get('user_perfil', '').strip().lower()

            is_admin = session.get('user_admin', False)
            if user_perfil not in perfis_validos and not is_admin:
                return jsonify({
                    'message': 'Acesso negado: você não tem permissão para acessar este recurso.'
                }), 403
            
            return view(*args, **kwargs)
        return decorated_function
    return decorator