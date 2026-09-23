from repository.setores_repository import SetoresRepository
from connection.conn import Connection
from flask_socketio import join_room
from extensions import socketio
from flask import session

def register_socket_events(sio=None):
    @socketio.on('connect')
    def handle_connect():
        user_id = session.get('user_id')

        if not user_id:
            return False  # Rejeita a conexão se o usuário não estiver autenticado

        try:
            conn = Connection().get_connection()
            setores_repository = SetoresRepository(conn)

            setores = setores_repository.get_setores_por_id_responsavel(user_id)
            for setor in setores:
                join_room(f"setor_{setor.id}")

        except Exception as e:
            print(f"Erro ao vincular salas de setor para usuário {user_id}: {e}")
            return False  # Rejeita a conexão em caso de erro

        finally:
            if conn:
                conn.close()

    @socketio.on('disconnect')
    def handle_disconnect():
        print('Cliente desconectado')