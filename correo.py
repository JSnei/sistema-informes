import os
import resend
import time
import uuid
from resend.exceptions import ResendError
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

    # Una clave por operación: todos sus reintentos representan el mismo correo.
    opciones = {"idempotency_key": str(uuid.uuid4())}
    for intento in range(3):
        try:
            return resend.Emails.send(params, opciones)
        except ResendError as error:
            # Credenciales, destinatarios y otros errores permanentes no se reintentan.
            estado = getattr(error, "code", None)
            try:
                temporal = int(estado) >= 500 or int(estado) in (408, 429)
            except (TypeError, ValueError):
                temporal = False
            if not temporal or intento == 2:
                raise
            time.sleep(1 + intento)