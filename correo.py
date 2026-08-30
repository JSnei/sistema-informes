import os
import resend
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

resend.api_key = RESEND_API_KEY


def enviar_codigo(destinatario, codigo):

    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY no está configurada")

    params = {
        "from": "Sistema de Informes <sistema@bselectromecanica.com>",
        "to": [destinatario],
        "subject": "Código de verificación - BS Electromecánica",
        "text": f"""
Hola,

Tu código de verificación para ingresar al sistema de formatos de
BS Electromecánica es:

{codigo}

Este código es personal y temporal.

Si no solicitaste este código, puedes ignorar este mensaje.

BS Electromecánica S.A.S.
""",
    }

    return resend.Emails.send(params)