"""Códigos de un uso para un proceso de aplicación (usar un solo worker)."""
import secrets
from datetime import datetime, timedelta, timezone
from threading import RLock

lock = RLock()


def crear_codigo(almacen, credencial, fecha=""):
    ahora = datetime.now(timezone.utc)
    with lock:
        anterior = almacen.get(credencial, {})
        ultimo = anterior.get("ultimo_envio")
        if ultimo and ahora - ultimo < timedelta(seconds=60):
            raise ValueError("Espera 60 segundos antes de solicitar otro código.")
        codigo = str(secrets.randbelow(900000) + 100000)
        almacen[credencial] = {"codigo": codigo, "fecha": fecha, "intentos": 0,
            "expira": ahora + timedelta(minutes=10), "ultimo_envio": ahora}
        return codigo


def invalidar_codigo(almacen, credencial):
    with lock:
        if credencial in almacen:
            almacen[credencial]["codigo"] = None


def comprobar_codigo(almacen, credencial, codigo):
    with lock:
        datos = almacen.get(credencial)
        if not datos or not datos.get("codigo"):
            raise ValueError("No hay un código activo. Solicita uno nuevo.")
        if not datos.get("expira") or datetime.now(timezone.utc) >= datos["expira"]:
            datos["codigo"] = None
            raise ValueError("El código venció. Solicita uno nuevo.")
        # compare_digest sobre bytes también admite entradas Unicode inválidas sin fallar.
        if not secrets.compare_digest(codigo.strip().encode(), datos["codigo"].encode()):
            datos["intentos"] += 1
            if datos["intentos"] >= 5:
                datos["codigo"] = None
                raise ValueError("Se superó el número máximo de intentos. Solicita un nuevo código.")
            raise ValueError(f"Código incorrecto. Te quedan {5 - datos['intentos']} intentos.")
        resultado = dict(datos)
        datos["codigo"] = None
        return resultado
