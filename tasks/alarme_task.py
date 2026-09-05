import paho.mqtt.publish as publish
import sys 
import os

BROKER_ADDRESS = os.environ.get("BROKER_ADDRESS", "localhost")  # Endereço do broker MQTT
PORT = int(os.environ.get("BROKER_PORT", 1883))  # Porta do broker MQTT

def enviar_comando(comando: str, endereco_esp32: str):
    """Função para enviar um comando via MQTT para o ESP32.
    Args:
        comando (str): O comando a ser enviado (ex: "DISPARAR", "RESET").
        endereco_esp32 (str): O endereço do ESP32 para o qual o comando será enviado.
    """
    
    try:
        topico = f"alarme/{endereco_esp32}/comando"

        publish.single(
            topic=topico,
            payload=comando,
            hostname=BROKER_ADDRESS,
            port=PORT,
            client_id="Python_Controlador"
        )

        print(f"Comando '{comando}' publicado com sucesso no topico '{topico}'")

    except Exception as e:
        print(f"Erro ao publicar comando: {e}")