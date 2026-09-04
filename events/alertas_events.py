from flask_socketio import emit
from extensions import socketio

def register_socket_events():
    @socketio.on('connect')
    def handle_connect():
        print('Cliente conectado')
        emit('connected', {'message': 'Conectado ao servidor de notificações'})

    @socketio.on('disconnect')
    def handle_disconnect():
        print('Cliente desconectado')