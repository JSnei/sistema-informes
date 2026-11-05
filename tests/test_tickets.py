"""Pruebas aisladas: SQLite en memoria; no usan PostgreSQL, correo ni Drive."""
import base64
import importlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import inspect, text

from database import database as db


class TicketsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(db, "crear_base_datos"):
            cls.main = importlib.import_module("main")

    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        db.Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db_patch = patch.object(db, "SessionLocal", self.sessions)
        self.db_patch.start()
        self.drive_patch = patch.object(self.main, "sincronizar_excel_seguro", return_value=True)
        self.drive_patch.start()
        with self.sessions() as session:
            session.add_all([
                db.Tienda(sap="1230", nombre="NEIVA GUADUALES", direccion="Calle 19 No 41A - 26", ciudad="Neiva"),
                db.Tienda(sap="1231", nombre="Otra tienda"),
                db.Tienda(sap="1232", nombre="Inactiva", activo=False)
            ])
            session.commit()
        self.client = TestClient(self.main.app)

    def tearDown(self):
        self.client.close()
        self.db_patch.stop()
        self.drive_patch.stop()
        self.engine.dispose()

    def autenticar(self, operador=False):
        sesion = {"admin_autenticado": True} if not operador else {
            "operador_autenticado": True, "operador_rol": "operador_servicios_externos",
            "operador_credencial": "400", "operador_inicio": datetime.now().isoformat()
        }
        valor = base64.b64encode(json.dumps(sesion).encode())
        cookie = TimestampSigner(self.main.SESSION_SECRET).sign(valor).decode()
        self.client.cookies.clear()
        self.client.cookies.set("session", cookie)

    def datos(self, numero="1294255", sap="1230"):
        return dict(numero=numero, sap_tienda=sap, prioridad="ALTA",
                    fecha_reporte="2026-11-01T21:51:03", equipo="ALQUILER DE PLANTA ELECTRICA - 600001273",
                    descripcion="Alquiler por corte programado", contacto="",
                    telefonos="3112104557 / 3143419538", registrado_por="TATIANA AÑEZ",
                    coordinador="COORDINADOR ZONA 1.7", codigo="")

    def registrar(self, numero="1294255", sap="1230"):
        db.registrar_ticket(**self.datos(numero, sap))
        return db.obtener_tickets()[0]["id"]

    def servicio(self, numero="1294255", solicitud=None, prueba=False):
        token = "token-" + str(len(db.obtener_enlaces_externos()))
        db.crear_enlace_externo(token, "PRUEBA" if prueba else "REAL")
        return db.crear_servicio_externo(
            token=token, sap_tienda="1230", ticket=numero,
            tipo_servicio="CORRECTIVO", cedula_tecnico="123", nombre_tecnico="Técnico", telefono_tecnico="3112104557",
            sap_encargado="456", nombre_encargado="Encargado", descripcion_falla="Falla",
            trabajo_realizado="Reparación", observaciones="", suministro_repuestos="NO",
            repuestos_suministrados="", ticket_solicitud_id=solicitud
        )

    def test_validaciones_y_realizado(self):
        self.registrar()
        with self.assertRaises(ValueError):
            db.registrar_ticket(**self.datos(" 1294255 "))
        with self.assertRaises(ValueError):
            db.consultar_ticket_servicio("no-existe", "1230")
        with self.assertRaises(ValueError):
            db.consultar_ticket_servicio("1294255", "1231")
        with self.assertRaises(ValueError):
            self.servicio("no-existe")
        self.assertEqual(db.consultar_ticket_servicio(" 1294255 ", "1230")[0]["numero"], "1294255")
        sid = self.servicio()
        self.assertEqual(db.obtener_tickets()[0]["estado"], "REALIZADO")
        with self.assertRaises(ValueError):
            self.servicio()
        db.anular_servicio_real(sid)
        self.assertEqual(db.obtener_tickets()[0]["estado"], "PENDIENTE")
        self.servicio()

    def test_varios_000_asignar_numero_y_anular(self):
        primero = self.registrar("000")
        segundo = self.registrar("000")
        self.assertNotEqual(primero, segundo)
        self.assertEqual(len(db.consultar_ticket_servicio("000", "1230")), 2)
        with self.assertRaises(ValueError):
            self.servicio("000")
        sid = self.servicio("000", primero)
        self.assertEqual(len(db.consultar_ticket_servicio("000", "1230")), 1)
        realizado = next(t for t in db.obtener_tickets() if t["id"] == primero)
        self.assertEqual(realizado["estado"], "REALIZADO")
        self.assertEqual(realizado["estado_ticket"], "FALTANTE POR NÚMERO DE TICKET")
        db.asignar_numero_ticket(primero, "1294255")
        with self.sessions() as session:
            self.assertEqual(session.get(db.Servicio, sid).ticket, "1294255")
        with self.assertRaises(ValueError):
            db.asignar_numero_ticket(segundo, "1294255")
        db.anular_servicio_real(sid)
        self.assertEqual(db.consultar_ticket_servicio("1294255", "1230")[0]["id"], primero)

    def test_pruebas_no_completan_ticket(self):
        solicitud = self.registrar("000")
        sid = self.servicio("000", solicitud, prueba=True)
        self.assertEqual(db.obtener_tickets()[0]["estado"], "PENDIENTE")
        db.eliminar_servicio_prueba(sid)
        self.servicio("000", solicitud)
        self.assertEqual(db.obtener_tickets()[0]["estado"], "REALIZADO")

    def test_oficina_busqueda_permisos_y_formulario(self):
        self.assertEqual(self.client.get("/admin/tickets", follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get("/admin/tickets/tienda?sap=1230", follow_redirects=False).status_code, 303)
        self.autenticar()
        tienda = self.client.get("/admin/tickets/tienda?sap=1230").json()
        self.assertEqual(tienda["ciudad"], "Neiva")
        self.assertEqual(self.client.get("/admin/tickets/tienda?sap=1232").status_code, 404)
        self.assertEqual(self.client.post("/admin/tickets", data=self.datos(), follow_redirects=False).status_code, 303)
        self.assertIn("1294255", self.client.get("/admin/tickets").text)
        self.assertEqual(self.client.post("/admin/tickets", data=self.datos()).status_code, 400)
        self.autenticar(operador=True)
        self.assertEqual(self.client.get("/admin/tickets").status_code, 200)
        self.assertEqual(self.client.get("/admin/tiendas", follow_redirects=False).status_code, 303)

    def test_endpoint_externo_y_guardado_directo(self):
        solicitud = self.registrar("000")
        db.crear_enlace_externo("externo")
        self.assertEqual(self.client.get("/s/falso/verificar-ticket?numero=000&sap=1230").status_code, 403)
        self.assertEqual(self.client.get("/s/externo/verificar-ticket?numero=000&sap=1231").status_code, 400)
        self.assertEqual(self.client.get("/s/externo/verificar-ticket?numero=000&sap=1230").json()["solicitudes"][0]["id"], solicitud)
        with self.sessions() as session:
            enlace = session.query(db.EnlaceExterno).filter_by(token="externo").one()
            enlace.fecha_creacion = datetime.now(timezone.utc) - timedelta(hours=25)
            session.commit()
        self.assertEqual(self.client.get("/s/externo/verificar-ticket?numero=000&sap=1230").status_code, 403)
        db.crear_enlace_externo("guardar")
        datos = dict(sap_tienda="1230", ticket="000", tipo_servicio="CORRECTIVO", cedula_tecnico="123",
                     nombre_tecnico="Técnico", telefono_tecnico="3112104557", sap_encargado="456", nombre_encargado="Encargado",
                     descripcion_falla="Falla", trabajo_realizado="Reparación", suministro_repuestos="NO")
        respuesta = self.client.post("/s/guardar/guardar-servicio", data=datos)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Selecciona la solicitud", respuesta.text)
        datos["ticket_solicitud_id"] = solicitud
        self.assertEqual(self.client.post("/s/guardar/guardar-servicio", data=datos).status_code, 200)
        self.assertEqual(db.obtener_tickets()[0]["estado"], "REALIZADO")

    def test_enlace_automatico_vinculado_y_un_solo_uso(self):
        primero = self.registrar("000")
        segundo = self.registrar("000")
        ticket = next(t for t in db.obtener_tickets() if t["id"] == primero)
        token = ticket["token"]
        self.assertTrue(token)
        respuesta = self.client.get(f"/s/{token}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('id="formulario-servicio"', respuesta.text)
        datos = self.client.get(f"/s/{token}/verificar-ticket?numero=000&sap=1230").json()
        self.assertEqual([s["id"] for s in datos["solicitudes"]], [primero])
        with self.assertRaisesRegex(ValueError, "solo permite"):
            db.crear_servicio_externo(token=token, sap_tienda="1230", ticket="000",
                tipo_servicio="CORRECTIVO", cedula_tecnico="1", nombre_tecnico="Técnico", telefono_tecnico="3112104557",
                sap_encargado="1", nombre_encargado="Encargado", descripcion_falla="Falla",
                trabajo_realizado="Trabajo", observaciones="", suministro_repuestos="NO",
                repuestos_suministrados="", ticket_solicitud_id=segundo)
        datos_servicio = dict(sap_tienda="1230", ticket="000", ticket_solicitud_id=primero,
            tipo_servicio="CORRECTIVO", cedula_tecnico="1", nombre_tecnico="Técnico", telefono_tecnico="3112104557",
            sap_encargado="1", nombre_encargado="Encargado", descripcion_falla="Falla",
            trabajo_realizado="Trabajo", suministro_repuestos="NO")
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos_servicio).status_code, 200)
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos_servicio).status_code, 403)
        self.assertEqual(self.client.get(f"/s/{token}").status_code, 403)
        self.assertEqual(self.client.get(f"/s/{token}/verificar-ticket?numero=000&sap=1230").status_code, 403)
        db.editar_ticket(primero, **self.datos("1294255", "1231"))
        self.assertEqual(self.client.get(f"/s/{token}").status_code, 403)
        with self.sessions() as session:
            servicio = session.query(db.Servicio).one()
            self.assertEqual(servicio.ticket, "1294255")
            self.assertEqual(session.get(db.Tienda, servicio.tienda_id).sap, "1231")

    def test_editar_desde_app_y_enlace_refleja_cambios(self):
        solicitud = self.registrar()
        token = db.obtener_tickets()[0]["token"]
        self.assertEqual(self.client.get(f"/admin/tickets/{solicitud}/editar", follow_redirects=False).status_code, 303)
        self.autenticar()
        respuesta = self.client.get(f"/admin/tickets/{solicitud}/editar")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Guardar cambios", respuesta.text)
        datos = self.datos("1294256", "1231")
        datos["equipo"] = "Equipo corregido"
        respuesta = self.client.post(f"/admin/tickets/{solicitud}/editar", data=datos, follow_redirects=False)
        self.assertEqual(respuesta.status_code, 303)
        self.assertEqual(db.obtener_tickets()[0]["token"], token)
        self.assertIn("Otra tienda", self.client.get(f"/s/{token}").text)
        self.assertIn("Equipo corregido", self.client.get(f"/s/{token}").text)
        self.assertEqual(self.client.get(f"/s/{token}/verificar-ticket?numero=1294255&sap=1230").status_code, 400)
        self.assertEqual(self.client.get(f"/s/{token}/verificar-ticket?numero=1294256&sap=1231").status_code, 200)
        datos["sap_tienda"] = "1232"
        self.assertEqual(self.client.post(f"/admin/tickets/{solicitud}/editar", data=datos).status_code, 400)
        self.assertEqual(db.obtener_tickets()[0]["sap"], "1231")
        self.registrar("OTRO")
        datos["sap_tienda"] = "1231"
        datos["numero"] = "OTRO"
        self.assertEqual(self.client.post(f"/admin/tickets/{solicitud}/editar", data=datos).status_code, 400)

    def test_telefono_obligatorio_y_ticket_fijo(self):
        self.registrar()
        token = db.obtener_tickets()[0]["token"]
        pagina = self.client.get(f"/s/{token}").text
        self.assertNotIn('Solicitud de la oficina', pagina)
        self.assertNotIn('id="ticket_solicitud_id"', pagina)
        self.assertNotIn('id="verificar-ticket"', pagina)
        from html.parser import HTMLParser
        campos = {}
        class Entradas(HTMLParser):
            def handle_starttag(self, tag, attrs):
                atributos = dict(attrs)
                if tag == "input":
                    campos[atributos.get("name")] = atributos
        Entradas().feed(pagina)
        self.assertIn("readonly", campos["ticket"])
        self.assertEqual(campos["ticket"]["value"], "1294255")
        self.assertEqual(campos["telefono_tecnico"]["type"], "tel")
        self.assertIn("required", campos["telefono_tecnico"])
        datos = dict(sap_tienda="1230", ticket="1294255", tipo_servicio="CORRECTIVO",
            cedula_tecnico="123", nombre_tecnico="Técnico", sap_encargado="456",
            nombre_encargado="Encargado", descripcion_falla="Falla",
            trabajo_realizado="Reparación", suministro_repuestos="NO")
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos).status_code, 422)
        datos["telefono_tecnico"] = "abc"
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos).status_code, 400)
        datos["telefono_tecnico"] = "+57 311 2104557"
        datos["ticket"] = "OTRO"
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos).status_code, 400)
        datos["ticket"] = "1294255"
        # No se necesita enviar el identificador de la solicitud: lo determina el enlace.
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos).status_code, 200)
        self.assertEqual(db.obtener_servicios()[0]["telefono_tecnico"], "+57 311 2104557")
        self.assertEqual(db.obtener_servicios_para_excel()[0]["telefono_tecnico"], "+57 311 2104557")

    def test_actualizar_base_existente_conserva_servicios(self):
        antigua = create_engine("sqlite://")
        try:
            with antigua.begin() as conexion:
                conexion.execute(text("CREATE TABLE servicios (id INTEGER PRIMARY KEY, ticket VARCHAR(100))"))
                conexion.execute(text("INSERT INTO servicios (id, ticket) VALUES (1, 'ANTERIOR')"))
            with patch.object(db, "engine", antigua):
                db.crear_base_datos()
                db.crear_base_datos()
            self.assertIn("telefono_tecnico", {c["name"] for c in inspect(antigua).get_columns("servicios")})
            with antigua.connect() as conexion:
                self.assertEqual(conexion.execute(text("SELECT ticket, telefono_tecnico FROM servicios")).one(), ("ANTERIOR", None))
        finally:
            antigua.dispose()


if __name__ == "__main__":
    unittest.main()
