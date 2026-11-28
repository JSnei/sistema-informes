import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import excel_drive
from scripts import autorizar_drive


class DriveAuthTest(unittest.TestCase):
    def test_oauth_utiliza_cuenta_autorizada(self):
        credenciales = SimpleNamespace(refresh_token="refresh-de-prueba")
        with patch.object(excel_drive, "GOOGLE_DRIVE_FOLDER_ID", "carpeta"), \
             patch.object(excel_drive, "GOOGLE_DRIVE_OAUTH_TOKEN", "/privado/token.json"), \
             patch.object(excel_drive.UserCredentials, "from_authorized_user_file", return_value=credenciales) as cargar, \
             patch.object(excel_drive.service_account.Credentials, "from_service_account_file") as servicio, \
             patch.object(excel_drive, "build") as construir:
            self.assertIs(excel_drive.obtener_drive(), construir.return_value)
            cargar.assert_called_once_with("/privado/token.json", scopes=excel_drive.DRIVE_SCOPES)
            self.assertIs(construir.call_args.kwargs["credentials"], credenciales)
            servicio.assert_not_called()

    def test_autorizacion_invalida_no_regresa_a_cuenta_de_servicio(self):
        with patch.object(excel_drive, "GOOGLE_DRIVE_FOLDER_ID", "carpeta"), \
             patch.object(excel_drive, "GOOGLE_DRIVE_OAUTH_TOKEN", "token.json"), \
             patch.object(excel_drive.UserCredentials, "from_authorized_user_file", return_value=SimpleNamespace(refresh_token=None)), \
             patch.object(excel_drive.service_account.Credentials, "from_service_account_file") as servicio:
            with self.assertRaises(RuntimeError):
                excel_drive.obtener_drive()
            servicio.assert_not_called()

    def test_conexion_anterior_disponible_sin_token_oauth(self):
        with patch.object(excel_drive, "GOOGLE_DRIVE_FOLDER_ID", "carpeta"), \
             patch.object(excel_drive, "GOOGLE_DRIVE_OAUTH_TOKEN", None), \
             patch.object(excel_drive.service_account.Credentials, "from_service_account_file") as servicio, \
             patch.object(excel_drive, "build") as construir:
            excel_drive.obtener_drive()
            self.assertIs(construir.call_args.kwargs["credentials"], servicio.return_value)

    def test_autorizacion_guarda_token_sin_imprimirlo(self):
        with TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            cliente = carpeta / "cliente.json"
            cliente.write_text(json.dumps({"installed": {"client_id": "cliente-de-prueba"}}), encoding="utf-8")
            destino = carpeta / "privado" / "token.json"
            credenciales = MagicMock()
            credenciales.refresh_token = "token-privado-de-prueba"
            credenciales.has_scopes.return_value = True
            credenciales.to_json.return_value = json.dumps({"refresh_token": credenciales.refresh_token})
            salida = io.StringIO()
            with patch("sys.argv", ["autorizar_drive.py", "--client", str(cliente), "--token", str(destino)]), \
                 patch.object(autorizar_drive.InstalledAppFlow, "from_client_config") as crear_flujo, \
                 contextlib.redirect_stdout(salida):
                crear_flujo.return_value.run_local_server.return_value = credenciales
                autorizar_drive.main()
            self.assertEqual(json.loads(destino.read_text())["refresh_token"], credenciales.refresh_token)
            self.assertNotIn(credenciales.refresh_token, salida.getvalue())
            self.assertEqual(list(destino.parent.iterdir()), [destino])
            opciones = crear_flujo.return_value.run_local_server.call_args.kwargs
            self.assertEqual(opciones["access_type"], "offline")
            self.assertEqual(opciones["host"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
