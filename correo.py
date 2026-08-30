import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

GMAIL_USUARIO = os.getenv("GMAIL_USUARIO")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def enviar_codigo(destinatario, codigo):

    mensaje = EmailMessage()

    mensaje["Subject"] = "Código de verificación - BS Electromecánica"
    mensaje["From"] = GMAIL_USUARIO
    mensaje["To"] = destinatario

    mensaje.set_content(
        f"""
Hola,

Tu código de verificación para ingresar al sistema de formatos de
BS Electromecánica es:

{codigo}

Si no solicitaste este código, puedes ignorar este mensaje.

BS Electromecánica S.A.S.
"""
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
        servidor.login(
            GMAIL_USUARIO,
            GMAIL_APP_PASSWORD
        )

        servidor.send_message(mensaje)
