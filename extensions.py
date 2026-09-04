from flask_socketio import SocketIO
import os

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

socketio = SocketIO()

def emitir_evento_global(evento: str, dados: dict):
    """
    Emite um evento no Redis para ser distribuída aos clientes WebSocket.
    Funciona no processo principal e em subprocessos (como o VisionWorker).

    Args:
        evento (str): O nome do evento a ser emitido.
        dados (dict): Os dados a serem enviados com o evento.
    """

    try:
        emitter = SocketIO(message_queue=REDIS_URL)
        emitter.emit(evento, dados, broadcast=True)

    except Exception as e:
        print(f"Erro ao emitir evento global: {e}")