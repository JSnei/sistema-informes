"""Autoriza la cuenta propietaria de Drive desde el navegador del computador."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from google_auth_oauthlib.flow import InstalledAppFlow
from excel_drive import DRIVE_SCOPES


def guardar_token(credenciales, destino):
    destino = Path(destino).resolve()
    destino.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporal = tempfile.mkstemp(dir=destino.parent, prefix=".token-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            archivo.write(credenciales.to_json())
        os.replace(temporal, destino)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)
    return destino


def main():
    parser = argparse.ArgumentParser(description="Autorizar Google Drive con la cuenta propietaria de las carpetas.")
    parser.add_argument("--client", default=".secrets/google-drive-client.json", help="JSON del cliente OAuth de tipo escritorio")
    parser.add_argument("--token", default=".secrets/google-drive-token.json", help="Archivo privado donde guardar la autorización")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true", help="Mostrar el enlace para abrirlo usando un túnel SSH")
    args = parser.parse_args()
    try:
        configuracion = json.loads(Path(args.client).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        parser.error("Guarda primero el JSON del cliente OAuth de escritorio en la ruta indicada por --client.")
    if "installed" not in configuracion:
        parser.error("El JSON debe ser de un cliente OAuth de tipo Aplicación de escritorio.")
    if args.no_browser and args.port == 0:
        parser.error("Para un túnel SSH indica un puerto fijo con --port.")
    flujo = InstalledAppFlow.from_client_config(configuracion, DRIVE_SCOPES, autogenerate_code_verifier=True)
    credenciales = flujo.run_local_server(host="127.0.0.1", port=args.port,
        open_browser=not args.no_browser, timeout_seconds=300, prompt="consent", access_type="offline",
        authorization_prompt_message="Abre este enlace e inicia sesión con la cuenta propietaria de las carpetas:\n{url}",
        success_message="Google Drive quedó autorizado. Puedes cerrar esta ventana.")
    if not credenciales.refresh_token or not credenciales.has_scopes(DRIVE_SCOPES):
        raise RuntimeError("La autorización no incluye acceso permanente a Drive. Vuelve a autorizar y acepta el permiso solicitado.")
    destino = guardar_token(credenciales, args.token)
    print(f"Autorización guardada en {destino}")
    print("Configura GOOGLE_DRIVE_OAUTH_TOKEN con la ruta de ese archivo y reinicia la aplicación.")
    print("El archivo contiene credenciales privadas. Transfiérelo por SSH y consérvalo fuera de Git.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"No se pudo completar la autorización ({type(error).__name__}). Revisa el permiso en Google y vuelve a intentarlo.", file=sys.stderr)
        raise SystemExit(1)
