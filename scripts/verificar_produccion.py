"""Diagnóstico sin secretos ni escrituras: python scripts/verificar_produccion.py --database."""
import argparse
import os
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from dotenv import load_dotenv

load_dotenv(RAIZ / ".env")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", action="store_true", help="Comprueba PostgreSQL en una transacción de solo lectura")
    args = parser.parse_args()
    fallos = []

    def comprobar(nombre, correcto):
        print(("OK   " if correcto else "FALTA ") + nombre)
        if not correcto:
            fallos.append(nombre)

    comprobar("Python 3.11 o superior para el SDK de Google instalado", sys.version_info >= (3, 11))
    comprobar("APP_ENV=production", os.getenv("APP_ENV", "").lower() == "production")
    comprobar("COOKIE_SECURE=true (requiere HTTPS)", os.getenv("COOKIE_SECURE", "").lower() == "true")
    comprobar("SESSION_SECRET de al menos 32 caracteres", len(os.getenv("SESSION_SECRET", "")) >= 32)
    for clave in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "ADMIN_EMAIL",
                  "OPERADOR_400_EMAIL", "RESEND_API_KEY", "GOOGLE_DRIVE_FOLDER_ID"):
        comprobar(clave + " configurada", bool(os.getenv(clave)))
    credenciales = Path(os.getenv("GOOGLE_DRIVE_CREDENTIALS", "/home/bsadmin/google-drive-credentials.json"))
    comprobar("Archivo de credenciales de Google Drive accesible", credenciales.is_file())
    if args.database:
        from sqlalchemy import create_engine, inspect, text
        from database.database import Base, url
        motor = create_engine(url, connect_args={"connect_timeout": 5})
        try:
            with motor.connect() as conexion:
                with conexion.begin():
                    conexion.execute(text("SET TRANSACTION READ ONLY"))
                    comprobar("Conexion PostgreSQL (solo lectura)", conexion.scalar(text("SELECT 1")) == 1)
                    inspector = inspect(conexion)
                    tablas = set(inspector.get_table_names())
                    for nombre, tabla in Base.metadata.tables.items():
                        existe = nombre in tablas
                        comprobar("Tabla " + nombre, existe)
                        if existe:
                            columnas = {c["name"] for c in inspector.get_columns(nombre)}
                            comprobar("Columnas de " + nombre, set(tabla.columns.keys()) <= columnas)
        except Exception as error:
            # No imprimir mensajes de conexión: pueden contener datos del servidor.
            print("FALTA Comprobacion PostgreSQL: " + type(error).__name__)
            fallos.append("PostgreSQL")
        finally:
            motor.dispose()
    print(f"\nResultado: {len(fallos)} requisito(s) pendiente(s).")
    print("Este diagnostico no prueba envios de correo, permisos remotos de Drive ni carga/concurrencia.")
    return bool(fallos)


if __name__ == "__main__":
    raise SystemExit(main())
