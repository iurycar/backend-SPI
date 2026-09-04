from email.message import EmailMessage
import smtplib
import os

def task_enviar_email_alerta_critico(
        email_destinatario: str, 
        nome_zona: str, 
        nome_camera: str, 
        nome_setor: str, 
        evento: str, 
        severidade: int):
    """
        Tarefa para enviar um e-mail de alerta crítico.
    
    Args:
        email_destinatario (str): Endereço de e-mail do destinatário.
        nome_zona (str): Nome da zona de monitoramento.
        nome_camera (str): Nome da câmera.
        nome_setor (str): Nome do setor.
        evento (str): Descrição do evento.
        severidade (int): Nível de severidade do alerta.
    """

    email_address = os.getenv('EMAIL_ADDRESS')
    token_senha = os.getenv('EMAIL_PASSWORD')

    if not (email_destinatario and email_address and token_senha):
        print("Informações de e-mail incompletas. Não é possível enviar o alerta crítico.")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Alerta Crítico - Evento: {evento}"
    msg["From"] = email_address
    msg["To"] = email_destinatario
    msg.set_content(
        f"Alerta de severidade crítica na zona de monitoramento:\n\n"
        f" - Zona: {nome_zona or 'Não especificado'}\n"
        f" - Câmera: {nome_camera or 'Não especificado'}\n"
        f" - Setor: {nome_setor or 'Não especificado'}\n"
        f" - Evento: {evento or 'Não especificado'}\n"
        f" - Severidade: {severidade}\n\n"
        f"Por favor, tome as medidas necessárias imediatamente."
    )

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(email_address, token_senha)
            server.send_message(msg)
            print(f"E-mail de alerta crítico enviado para {email_destinatario}.")
    except Exception as e:
        print(f"Erro ao enviar e-mail de alerta crítico: {e}")
