"""Regresiones de acceso, OTP, formularios y exportación para la salida a producción."""
import base64
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from itsdangerous import TimestampSigner
from openpyxl import load_workbook

import auth_codes
import excel_drive
from database import database as db
import test_tickets as fixtures


class ProduccionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TicketsTest.setUpClass()
        cls.main = fixtures.TicketsTest.main

    setUp = fixtures.TicketsTest.setUp
    tearDown = fixtures.TicketsTest.tearDown
    autenticar = fixtures.TicketsTest.autenticar
    registrar = fixtures.TicketsTest.registrar
    datos = fixtures.TicketsTest.datos
    servicio = fixtures.TicketsTest.servicio

    def limpiar_codigos(self):
        self.main.codigo_administradores.clear()
        self.main.codigo_operadores.clear()
        self.main.codigo_tecnicos.clear()

    def test_todas_las_rutas_admin_exigen_sesion(self):
        for ruta in self.main.app.routes:
            if not ruta.path.startswith("/admin") or ruta.path in self.main.RUTAS_ADMIN_PUBLICAS:
                continue
            url = ruta.path
            for parametro in getattr(ruta, "param_convertors", {}):
                url = url.replace("{" + parametro + "}", "1")
            for metodo in ruta.methods & {"GET", "POST"}:
                with self.subTest(ruta=url, metodo=metodo):
                    respuesta = self.client.request(metodo, url, follow_redirects=False)
                    self.assertEqual(respuesta.status_code, 303)
                    self.assertEqual(respuesta.headers["location"], "/admin")

    def test_cookie_manipulada_no_autoriza(self):
        self.client.cookies.set("session", base64.b64encode(b'{"admin_autenticado":true}').decode() + '.invalida')
        self.assertEqual(self.client.get("/admin/tickets", follow_redirects=False).status_code, 303)

    def test_operador_expirado_no_usa_rutas_ni_crea_enlaces(self):
        sesion = {"operador_autenticado": True, "operador_rol": "operador_servicios_externos",
                  "operador_credencial": "400", "operador_inicio": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}
        cookie = TimestampSigner(self.main.SESSION_SECRET).sign(base64.b64encode(json.dumps(sesion).encode())).decode()
        for ruta in ["/admin/tickets", "/admin/servicios-externos", "/panel-operador", "/operador/servicios"]:
            self.client.cookies.clear()
            self.client.cookies.set("session", cookie)
            self.assertEqual(self.client.get(ruta, follow_redirects=False).status_code, 303)

    def test_admin_otp_caduca_cooldown_intentos_y_reuso(self):
        self.limpiar_codigos()
        with patch.object(self.main, "enviar_codigo") as enviar:
            self.assertEqual(self.client.post("/admin/enviar-codigo").status_code, 200)
            codigo = self.main.codigo_administradores["admin"]["codigo"]
            self.assertEqual(self.client.post("/admin/enviar-codigo").status_code, 429)
            self.assertEqual(enviar.call_count, 1)
            self.assertEqual(self.client.post("/admin/verificar-codigo", data={"codigo": "ñ"}).status_code, 400)
            self.assertEqual(self.client.post("/admin/verificar-codigo", data={"codigo": codigo}, follow_redirects=False).status_code, 303)
            self.assertEqual(self.client.get("/admin/panel").status_code, 200)
            self.assertEqual(self.client.post("/admin/verificar-codigo", data={"codigo": codigo}).status_code, 400)
            self.assertEqual(self.client.post("/admin/cerrar-sesion", follow_redirects=False).status_code, 303)
            self.assertEqual(self.client.get("/admin/panel", follow_redirects=False).status_code, 303)

    def test_otp_expiracion_y_cinco_intentos(self):
        almacen = {}
        codigo = auth_codes.crear_codigo(almacen, "101")
        almacen["101"]["expira"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError, "venció"):
            auth_codes.comprobar_codigo(almacen, "101", codigo)
        almacen.clear()
        codigo = auth_codes.crear_codigo(almacen, "101")
        for _ in range(5):
            with self.assertRaises(ValueError):
                auth_codes.comprobar_codigo(almacen, "101", "000000")
        with self.assertRaises(ValueError):
            auth_codes.comprobar_codigo(almacen, "101", codigo)
        with self.assertRaises(ValueError):
            auth_codes.crear_codigo(almacen, "101")

    def test_fallo_correo_no_deja_codigo_utilizable(self):
        self.limpiar_codigos()
        with patch.object(self.main, "enviar_codigo", side_effect=RuntimeError("fallo simulado")):
            self.assertEqual(self.client.post("/admin/enviar-codigo").status_code, 502)
            self.assertIsNone(self.main.codigo_administradores["admin"]["codigo"])

    def test_codigo_solo_un_login_ante_verificaciones_simultaneas(self):
        from concurrent.futures import ThreadPoolExecutor
        almacen = {}
        codigo = auth_codes.crear_codigo(almacen, "101")
        def verificar():
            try:
                auth_codes.comprobar_codigo(almacen, "101", codigo)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            self.assertEqual(sum(ejecutor.map(lambda _: verificar(), range(2))), 1)

    def test_acceso_tecnico_y_suplantacion(self):
        self.limpiar_codigos()
        tecnico = db.agregar_tecnico("101", "Tecnico prueba", "test@example.invalid", "locativo_cedi")
        otro = db.agregar_tecnico("102", "Otro tecnico", "otro@example.invalid", "locativo_cedi")
        datos = {"id_tecnico": tecnico.id, "fecha": "2026-11-10", "equipo": "Bomba",
                 "trabajo_realizado": " ".join(["Trabajo"] * 25)}
        self.assertEqual(self.client.post("/generar-mensaje", data=datos, follow_redirects=False).status_code, 303)
        with patch.object(self.main, "enviar_codigo"):
            self.assertEqual(self.client.post("/iniciar-servicio", data={"credencial": "101", "fecha": "2026-11-10"}).status_code, 200)
        codigo = self.main.codigo_tecnicos["101"]["codigo"]
        self.assertEqual(self.client.post("/verificar-tecnico", data={"credencial": "101", "codigo": codigo}).status_code, 200)
        self.assertEqual(self.client.post("/generar-mensaje", data=dict(datos, id_tecnico=otro.id), follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post("/generar-mensaje", data=dict(datos, trabajo_realizado="breve")).status_code, 400)
        self.assertEqual(self.client.post("/generar-mensaje", data=datos).status_code, 200)
        self.assertEqual(self.client.post("/verificar-tecnico", data={"credencial": "101", "codigo": codigo}).status_code, 400)

    def test_operador_401_usa_su_panel_y_no_admin(self):
        self.limpiar_codigos()
        db.agregar_tecnico("401", "Operador prueba", "operador@example.invalid", "operador_servicios_externos")
        with patch.object(self.main, "enviar_codigo"):
            self.assertEqual(self.client.post("/iniciar-servicio", data={"credencial": "401", "fecha": "2026-11-10"}).status_code, 200)
        codigo = self.main.codigo_operadores["401"]["codigo"]
        self.assertEqual(self.client.post("/verificar-tecnico", data={"credencial": "401", "codigo": codigo}, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get("/panel-operador").status_code, 200)
        self.assertEqual(self.client.get("/admin/tickets").status_code, 200)
        self.assertEqual(self.client.get("/admin/tecnicos", follow_redirects=False).status_code, 303)

    def test_formularios_y_campos_externos_se_validan(self):
        self.registrar()
        with self.assertRaises(ValueError):
            db.crear_servicio_externo(token=db.obtener_tickets()[0]["token"], sap_tienda="1230", ticket="1294255",
                tipo_servicio="X" * 51, cedula_tecnico="1", nombre_tecnico="Tecnico",
                telefono_tecnico="3112104557", sap_encargado="1", nombre_encargado="Encargado",
                descripcion_falla="Falla", trabajo_realizado="Trabajo", observaciones="",
                suministro_repuestos="NO", repuestos_suministrados="")
        self.assertEqual(db.obtener_tickets()[0]["estado"], "PENDIENTE")
        self.autenticar()
        campos = self.datos(numero="DISTINTO")
        campos["equipo"] = '<script>alert("xss")</script>'
        db.registrar_ticket(**campos)
        pagina = self.client.get("/admin/tickets").text
        self.assertNotIn('<script>alert("xss")</script>', pagina)
        self.assertIn("&lt;script&gt;", pagina)
        self.assertEqual(self.client.post("/admin/agregar-tecnico", data={"credencial":"999", "nombre":"Prueba", "correo":"test@example.invalid", "rol":"locativo_cedi"}).status_code, 400)

    def test_filtros_precios_y_descarga_excel(self):
        a = self.registrar("100")
        self.registrar("000")
        self.registrar("200")
        self.servicio("200")
        db.actualizar_precio_ticket(a, "0")
        self.autenticar()
        for filtro, cantidad in {"todos":3, "pendientes":2, "realizados":1, "sin-numero":1, "sin-precio":2}.items():
            respuesta = self.client.get("/admin/tickets", params={"filtro":filtro})
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(len(respuesta.context["tickets_visibles"]), cantidad)
        respuesta = self.client.get("/admin/tickets/excel")
        self.assertEqual(respuesta.status_code, 200)
        from io import BytesIO
        self.assertEqual(load_workbook(BytesIO(respuesta.content)).active.max_row, 4)
        for precio in ["-1", "NaN", "Infinity", "10000000000", "1.001"]:
            self.assertEqual(self.client.post(f"/admin/tickets/{a}/precio", data={"precio":precio}).status_code, 400)

    def test_exportacion_drive_no_interpreta_formulas(self):
        self.registrar()
        self.servicio()
        datos = db.obtener_servicios_para_excel()
        datos[0]["observaciones"] = '=HYPERLINK("https://example.invalid")'
        with patch.object(excel_drive, "obtener_servicios_para_excel", return_value=datos):
            hoja = load_workbook(excel_drive.generar_excel_servicios()).active
        self.assertEqual(hoja.cell(2, 19).data_type, "s")

    def test_plantillas_y_archivos_estaticos(self):
        for nombre in self.main.templates.env.list_templates():
            self.main.templates.env.get_template(nombre)
        for url in ["/", "/tecnico", "/admin", "/static/css/style.css", "/static/img/logo.png", "/static/js/tickets_oficina.js", "/static/js/ticket_servicio.js"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_generadores_anteriores_dirigen_al_ticket(self):
        self.autenticar()
        for metodo, ruta in [("GET", "/admin/servicios-externos"), ("POST", "/admin/servicios-externos/generar")]:
            respuesta = self.client.request(metodo, ruta, follow_redirects=False)
            self.assertEqual(respuesta.status_code, 303)
            self.assertEqual(respuesta.headers["location"], "/admin/tickets")
        self.autenticar(operador=True)
        respuesta = self.client.post("/operador/servicios-externos/generar", follow_redirects=False)
        self.assertEqual(respuesta.headers["location"], "/admin/tickets")
        self.assertEqual(len(db.obtener_enlaces_externos()), 0)


if __name__ == "__main__":
    unittest.main()
