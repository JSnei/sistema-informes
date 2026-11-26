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


def cuatro_fotos():
    contenido = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=")
    evidencias = [("fotos", (f"foto-{i}.png", contenido, "image/png")) for i in range(4)]
    return evidencias + [("fotos_ticket", ("firmado.png", contenido, "image/png"))]


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
        self.evidencia_patch = patch.object(self.main, "sincronizar_evidencia", return_value=True)
        self.evidencia_patch.start()
        with self.sessions() as session:
            session.add_all([
                db.Tienda(sap="1230", nombre="NEIVA GUADUALES", direccion="Calle 19 No 41A - 26", ciudad="Neiva"),
                db.Tienda(sap="1231", nombre="Otra tienda"),
                db.Tienda(sap="1232", nombre="Inactiva", activo=False)
            ])
            session.commit()
        self.client = TestClient(self.main.app, base_url="https://testserver")

    def tearDown(self):
        self.client.close()
        self.db_patch.stop()
        self.drive_patch.stop()
        self.evidencia_patch.stop()
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

    def test_renovar_enlace_invalida_anterior_y_conserva_ticket(self):
        solicitud = self.registrar("000")
        db.actualizar_precio_ticket(solicitud, "150000")
        original = db.obtener_tickets()[0]
        anterior = original["token"]
        ruta = f"/admin/tickets/{solicitud}/renovar-enlace"
        self.assertEqual(self.client.post(ruta, follow_redirects=False).status_code, 303)
        self.assertEqual(db.obtener_tickets()[0]["token"], anterior)
        self.autenticar(operador=True)
        self.assertEqual(self.client.post(ruta, follow_redirects=False).status_code, 303)
        actualizado = db.obtener_tickets()[0]
        nuevo = actualizado["token"]
        self.assertNotEqual(nuevo, anterior)
        for campo in ("id", "numero", "sap", "equipo", "descripcion", "precio", "estado"):
            self.assertEqual(actualizado[campo], original[campo])
        self.assertIsNone(db.obtener_enlace_externo(anterior))
        self.assertEqual(self.client.get(f"/s/{anterior}").status_code, 404)
        self.assertEqual(self.client.get(f"/s/{anterior}/verificar-ticket?numero=000&sap=1230").status_code, 403)
        self.assertEqual(self.client.get(f"/s/{nuevo}").status_code, 200)
        datos = dict(sap_tienda="1230", ticket="000", tipo_servicio="CORRECTIVO",
            cedula_tecnico="123", nombre_tecnico="Técnico", telefono_tecnico="3112104557",
            sap_encargado="456", nombre_encargado="Encargado", descripcion_falla="Falla",
            trabajo_realizado="Reparación", suministro_repuestos="NO")
        self.assertEqual(self.client.post(f"/s/{anterior}/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 404)
        self.assertEqual(self.client.post(f"/s/{nuevo}/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 200)
        self.assertEqual(self.client.post(ruta).status_code, 400)
        self.assertEqual(db.obtener_tickets()[0]["token"], nuevo)
        self.assertEqual(self.client.get(f"/s/{nuevo}").status_code, 403)
        self.assertEqual(self.client.post(f"/s/{nuevo}/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 403)

    def test_renovar_enlace_cancelado(self):
        solicitud = self.registrar()
        viejo = db.obtener_tickets()[0]["token"]
        db.cancelar_enlace_externo(db.obtener_enlace_externo(viejo).id)
        db.renovar_enlace_ticket(solicitud)
        nuevo = db.obtener_tickets()[0]["token"]
        self.assertNotEqual(nuevo, viejo)
        self.assertEqual(self.client.get(f"/s/{viejo}").status_code, 404)
        self.assertEqual(self.client.get(f"/s/{nuevo}").status_code, 200)
        with self.assertRaises(ValueError):
            db.renovar_enlace_ticket(99999)

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
        self.assertEqual(self.client.get("/s/externo/verificar-ticket?numero=000&sap=1230").status_code, 200)
        db.crear_enlace_externo("guardar")
        datos = dict(sap_tienda="1230", ticket="000", tipo_servicio="CORRECTIVO", cedula_tecnico="123",
                     nombre_tecnico="Técnico", telefono_tecnico="3112104557", sap_encargado="456", nombre_encargado="Encargado",
                     descripcion_falla="Falla", trabajo_realizado="Reparación", suministro_repuestos="NO")
        respuesta = self.client.post("/s/guardar/guardar-servicio", data=datos, files=cuatro_fotos())
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Selecciona la solicitud", respuesta.text)
        datos["ticket_solicitud_id"] = solicitud
        self.assertEqual(self.client.post("/s/guardar/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 200)
        self.assertEqual(db.obtener_tickets()[0]["estado"], "REALIZADO")

    def test_enlace_automatico_vinculado_y_un_solo_uso(self):
        primero = self.registrar("000")
        segundo = self.registrar("000")
        ticket = next(t for t in db.obtener_tickets() if t["id"] == primero)
        token = ticket["token"]
        self.assertTrue(token)
        with self.sessions() as session:
            enlace = session.query(db.EnlaceExterno).filter_by(token=token).one()
            enlace.fecha_creacion = datetime.now(timezone.utc) - timedelta(days=365)
            session.commit()
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
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos_servicio, files=cuatro_fotos()).status_code, 200)
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos_servicio, files=cuatro_fotos()).status_code, 403)
        self.assertEqual(self.client.get(f"/s/{token}").status_code, 403)
        self.assertEqual(self.client.get(f"/s/{token}/verificar-ticket?numero=000&sap=1230").status_code, 403)
        # Un enlace antiguo cancelado tampoco se vuelve válido.
        otro_token = next(t["token"] for t in db.obtener_tickets() if t["id"] == segundo)
        otro_enlace = db.obtener_enlace_externo(otro_token)
        db.cancelar_enlace_externo(otro_enlace.id)
        self.assertEqual(self.client.get(f"/s/{otro_token}").status_code, 403)
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
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 422)
        datos["telefono_tecnico"] = "abc"
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 400)
        datos["telefono_tecnico"] = "+57 311 2104557"
        datos["ticket"] = "OTRO"
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 400)
        datos["ticket"] = "1294255"
        # No se necesita enviar el identificador de la solicitud: lo determina el enlace.
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 200)
        self.assertEqual(db.obtener_servicios()[0]["telefono_tecnico"], "+57 311 2104557")
        self.assertEqual(db.obtener_servicios_para_excel()[0]["telefono_tecnico"], "+57 311 2104557")

    def test_editar_informe_del_tecnico(self):
        solicitud = self.registrar()
        token = db.obtener_tickets()[0]["token"]
        datos = dict(sap_tienda="1230", ticket="1294255", tipo_servicio="CORRECTIVO",
            cedula_tecnico="123", nombre_tecnico="Técnico", telefono_tecnico="3112104557",
            sap_encargado="456", nombre_encargado="Encargado", descripcion_falla="Falla",
            trabajo_realizado="Reparación", suministro_repuestos="NO")
        self.assertEqual(self.client.post(f"/s/{token}/guardar-servicio", data=datos, files=cuatro_fotos()).status_code, 200)
        ruta = f"/admin/tickets/{solicitud}/informe/editar"
        original = db.obtener_informe_ticket(solicitud)
        self.assertEqual(self.client.get(ruta, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post(ruta, data=original, follow_redirects=False).status_code, 303)
        self.assertEqual(db.obtener_informe_ticket(solicitud), original)
        self.autenticar(operador=True)
        self.assertEqual(self.client.get(ruta).status_code, 200)
        corregido = dict(original, cedula_tecnico="999", nombre_tecnico="Nombre corregido",
            telefono_tecnico="+57 314 3419538", tipo_servicio="PREVENTIVO", sap_encargado="888",
            nombre_encargado="Otra persona", descripcion_falla="Falla corregida",
            trabajo_realizado="Trabajo corregido", observaciones="Observación corregida",
            suministro_repuestos="SI", repuestos_suministrados="Contactor")
        self.assertEqual(self.client.post(ruta, data=dict(corregido, ticket="OTRO", estado="PENDIENTE"), follow_redirects=False).status_code, 303)
        self.assertEqual(db.obtener_informe_ticket(solicitud), corregido)
        exportado = db.obtener_servicios_para_excel()[0]
        self.assertEqual(exportado["trabajo_realizado"], "Trabajo corregido")
        self.assertEqual(exportado["nombre_tecnico"], "Nombre corregido")
        self.assertEqual(exportado["ticket"], "1294255")
        self.assertEqual(db.obtener_tickets()[0]["estado"], "REALIZADO")
        self.assertEqual(db.obtener_tickets()[0]["token"], token)
        self.assertEqual(self.client.get(f"/s/{token}").status_code, 403)
        self.assertEqual(self.client.post(ruta, data=dict(corregido, repuestos_suministrados="")).status_code, 400)
        self.assertEqual(self.client.post(ruta, data=dict(corregido, telefono_tecnico="abc")).status_code, 400)
        self.assertEqual(db.obtener_informe_ticket(solicitud), corregido)
        self.assertEqual(self.client.post(ruta, data=dict(corregido, suministro_repuestos="NO"), follow_redirects=False).status_code, 303)
        self.assertEqual(db.obtener_informe_ticket(solicitud)["repuestos_suministrados"], "")

    def test_informe_pendiente_o_anulado_no_se_edita(self):
        solicitud = self.registrar()
        self.autenticar()
        ruta = f"/admin/tickets/{solicitud}/informe/editar"
        self.assertEqual(self.client.get(ruta).status_code, 404)
        servicio_id = self.servicio()
        self.assertEqual(self.client.get(ruta).status_code, 200)
        db.anular_servicio_real(servicio_id)
        self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_evidencia_obligatoria_reintento_y_edicion(self):
        from types import SimpleNamespace
        from googleapiclient.errors import HttpError
        from httplib2 import Response
        import evidencia_drive

        solicitud = self.registrar("000")
        token = db.obtener_tickets()[0]["token"]
        ruta = f"/s/{token}/guardar-servicio"
        datos = dict(sap_tienda="1230", ticket="000", tipo_servicio="CORRECTIVO",
                     cedula_tecnico="123", nombre_tecnico="Técnico", telefono_tecnico="3112104557",
                     sap_encargado="456", nombre_encargado="Encargado", descripcion_falla="Falla",
                     trabajo_realizado="Reparación", suministro_repuestos="NO")
        vacio = [("fotos", ("vacio.pdf", b"", "application/pdf"))]
        self.assertEqual(self.client.post(ruta, data=datos, files=vacio).status_code, 400)
        with patch('evidencia_drive.MAX_TOTAL', 10):
            self.assertEqual(self.client.post(ruta, data=datos, files=cuatro_fotos()).status_code, 400)
        self.assertEqual(db.obtener_enlace_externo(token).estado, "PENDIENTE")
        pagina = self.client.get(f"/s/{token}").text
        self.assertEqual(pagina.count('name="fotos"'), 1)
        self.assertIn('multiple>', pagina)
        adjuntos = cuatro_fotos()
        adjuntos[-1] = ('fotos_ticket', ('firmado.pdf', b'%PDF-1.7\nFirmado', 'application/pdf'))
        adjuntos.append(('fotos', ('notas.txt', b'Notas del servicio', 'text/plain')))
        respuesta = self.client.post(ruta, data=datos, files=adjuntos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Recibimos 5 archivos de evidencia y 1 archivos del ticket firmado", respuesta.text)
        servicio_id = db.obtener_tickets()[0]["servicio_id"]
        fecha_envio = datetime.now(timezone.utc)
        with self.sessions() as session:
            session.get(db.Servicio, servicio_id).fecha_registro = fecha_envio
            session.commit()
        mes_envio = evidencia_drive.MESES[fecha_envio.astimezone(timezone(timedelta(hours=-5))).month - 1]
        ano_envio = str(fecha_envio.astimezone(timezone(timedelta(hours=-5))).year)
        guardados = {
            "ano": {"id": "ano", "name": ano_envio, "parents": ["padre"], "mimeType": "application/vnd.google-apps.folder"},
            "mes": {"id": "mes", "name": mes_envio, "parents": ["ano"], "mimeType": "application/vnd.google-apps.folder"},
        }
        fallar = True
        contador = 0

        def generar_ids(count, **opciones):
            nonlocal contador
            ids = [f"drive{i}" for i in range(contador + 1, contador + count + 1)]
            contador += count
            return SimpleNamespace(execute=lambda: {"ids": ids})

        def listar(q, **opciones):
            padre = q.split("'")[1]
            encontrados = [dict(d, id=id) for id, d in guardados.items() if padre in d.get("parents", [])]
            if "mimeType=" in q:
                encontrados = [d for d in encontrados if d.get("mimeType") == "application/vnd.google-apps.folder"]
            return SimpleNamespace(execute=lambda: {"files": encontrados})

        def crear(body, **opciones):
            def ejecutar():
                if body["id"] in guardados:
                    raise HttpError(Response({"status": "409"}), b"{}")
                if body["name"] == "2.png" and fallar:
                    raise OSError("Carga interrumpida")
                if body['name'] == 'F1.pdf':
                    self.assertEqual(opciones['media_body'].mimetype(), 'application/pdf')
                if body['name'] == '5.txt':
                    self.assertEqual(opciones['media_body'].mimetype(), 'text/plain')
                guardados[body["id"]] = dict(body)
                return {"id": body["id"]}
            return SimpleNamespace(execute=ejecutar)

        archivos = SimpleNamespace(
            generateIds=generar_ids,
            list=listar,
            create=crear,
            get=lambda fileId, **kw: SimpleNamespace(execute=lambda: guardados[fileId]),
            update=lambda fileId, body, **kw: SimpleNamespace(execute=lambda: guardados[fileId].update(body)),
        )
        with patch.object(evidencia_drive, "obtener_drive", return_value=SimpleNamespace(files=lambda: archivos)), \
             patch.object(evidencia_drive, "GOOGLE_DRIVE_FOLDER_ID", "padre"), \
             patch.dict("os.environ", {"GOOGLE_DRIVE_EVIDENCE_FOLDER_ID": "padre"}):
            with self.assertLogs("evidencia_drive", level="ERROR"):
                self.assertFalse(evidencia_drive.sincronizar_evidencia(servicio_id))
            self.assertTrue(db.obtener_tickets()[0]["evidencia_pendiente"])
            self.assertEqual(len(guardados), 4)
            fallar = False
            self.assertTrue(evidencia_drive.sincronizar_evidencia(servicio_id))
            self.assertEqual(len(guardados), 9)
            self.assertEqual(db.obtener_tickets()[0]["carpeta_evidencia"], "drive1")
            self.assertEqual(guardados["drive1"]["name"], f"000 - Solicitud {solicitud}")
            self.assertEqual(guardados["drive1"]["parents"], ["mes"])
            self.assertEqual(guardados["mes"]["parents"], ["ano"])
            self.assertEqual(guardados["ano"]["parents"], ["padre"])
            self.assertTrue({"1.png", "2.png", "3.png", "4.png", "5.txt", "F1.pdf"}.issubset({d["name"] for d in guardados.values()}))
            db.asignar_numero_ticket(solicitud, "1294255")
            self.assertTrue(evidencia_drive.sincronizar_evidencia(servicio_id))
            self.assertEqual(guardados["drive1"]["name"], "1294255")
            self.assertEqual(len(guardados), 9)
        with self.sessions() as session:
            fotos = session.query(db.FotoEvidencia).filter_by(servicio_id=servicio_id).all()
            self.assertEqual(len(fotos), 6)
            self.assertTrue(all(foto.contenido is None for foto in fotos))

    def test_cancelar_ticket_pendiente_conserva_registro_y_permite_eliminar(self):
        solicitud = self.registrar()
        anterior = db.obtener_tickets()[0]
        token = anterior["token"]
        ruta = f"/admin/tickets/{solicitud}/cancelar"
        self.assertEqual(self.client.post(ruta, follow_redirects=False).status_code, 303)
        self.assertEqual(db.obtener_tickets()[0]["estado"], "PENDIENTE")
        self.autenticar()
        self.assertEqual(self.client.post(ruta, follow_redirects=False).status_code, 303)
        cancelado = db.obtener_tickets()[0]
        self.assertEqual(cancelado["estado"], "CANCELADO")
        for campo in ("id", "numero", "sap", "equipo", "descripcion", "token"):
            self.assertEqual(cancelado[campo], anterior[campo])
        self.assertEqual(self.client.get(f"/s/{token}").status_code, 403)
        with self.assertRaises(ValueError):
            self.servicio()
        self.assertEqual(self.client.post(f"/admin/tickets/{solicitud}/renovar-enlace").status_code, 400)
        pagina = self.client.get("/admin/tickets?filtro=cancelados")
        self.assertEqual(len(pagina.context["tickets_visibles"]), 1)
        self.assertIn(f'/admin/tickets/{solicitud}/eliminar', pagina.text)
        self.assertNotIn('>Cancelar ticket<', pagina.text)
        self.assertEqual(self.client.get("/admin/tickets?filtro=pendientes").context["pendientes"], 0)
        db.editar_ticket(solicitud, **self.datos())
        self.assertEqual(db.obtener_tickets()[0]["estado"], "CANCELADO")
        self.assertEqual(db.obtener_tickets_para_excel()[0]["estado"], "CANCELADO")
        self.assertEqual(self.client.post(f"/admin/tickets/{solicitud}/eliminar", follow_redirects=False).status_code, 303)
        self.assertEqual(db.obtener_tickets(), [])

    def test_archivos_video_pdf_y_ticket_opcional(self):
        from io import BytesIO
        from types import SimpleNamespace
        from evidencia_drive import leer_adjuntos
        def subido(contenido, nombre='archivo'):
            return SimpleNamespace(file=BytesIO(contenido), filename=nombre)
        png = cuatro_fotos()[0][1][1]
        video = b'\x00\x00\x00\x18ftypisom' + b'\x00' * 24
        evidencias, firmadas = leer_adjuntos(
            [subido(png) for _ in range(3)] + [subido(video)], [subido(png), subido(png)])
        self.assertEqual(evidencias[-1][0], 'mp4')
        self.assertEqual(len(firmadas), 2)
        self.assertEqual(leer_adjuntos([], []), ([], []))
        self.assertEqual(leer_adjuntos([''], ['']), ([], []))
        evidencias, ticket = leer_adjuntos([subido(b'%PDF-1.7\nDocumento')], [subido(b'contenido', 'hoja.docx')])
        self.assertEqual(evidencias[0][0], 'pdf')
        self.assertEqual(ticket[0][0], 'docx')
        self.assertEqual(leer_adjuntos([subido(png)], [])[1], [])

    def test_envio_sin_archivos_un_adjunto_y_pdf_firmado(self):
        contenido_pdf = b'%PDF-1.7\nDocumento de prueba'
        casos = [[], [('fotos', ('evidencia.pdf', contenido_pdf, 'application/pdf'))],
                 [('fotos_ticket', ('firmado.pdf', contenido_pdf, 'application/pdf'))],
                 [('fotos', ('notas.txt', b'Notas', 'text/plain'))],
                 [('fotos', ('', b'', 'application/octet-stream')), ('fotos_ticket', ('', b'', 'application/octet-stream'))]]
        for indice, adjuntos in enumerate(casos):
            with self.subTest(adjuntos=indice):
                numero = str(9000 + indice)
                solicitud = self.registrar(numero)
                token = db.obtener_tickets()[0]['token']
                datos = dict(sap_tienda='1230', ticket=numero, tipo_servicio='CORRECTIVO',
                    cedula_tecnico='123', nombre_tecnico='Técnico', telefono_tecnico='3112104557',
                    sap_encargado='456', nombre_encargado='Encargado', descripcion_falla='Falla',
                    trabajo_realizado='Reparación', suministro_repuestos='NO')
                respuesta = self.client.post(f'/s/{token}/guardar-servicio', data=datos, files=adjuntos)
                self.assertEqual(respuesta.status_code, 200)
                ticket = next(t for t in db.obtener_tickets() if t['id'] == solicitud)
                self.assertEqual(ticket['estado'], 'REALIZADO')
                with self.sessions() as sesion:
                    archivos = sesion.query(db.FotoEvidencia).filter_by(servicio_id=ticket['servicio_id']).all()
                    if indice in (0, 4):
                        self.assertEqual(archivos, [])
                    else:
                        self.assertEqual(len(archivos), 1)
                        if indice == 2:
                            self.assertEqual(archivos[0].tipo, 'FIRMADO')
                            self.assertEqual(archivos[0].formato, 'pdf')
                            self.assertIn('1 archivos del ticket firmado', respuesta.text)

    def test_directorio_mensual_reintenta_mismo_id(self):
        from unittest.mock import MagicMock
        from evidencia_drive import obtener_directorio
        archivos = MagicMock()
        archivos.list.return_value.execute.return_value = {'files': []}
        archivos.generateIds.return_value.execute.return_value = {'ids': ['mes-nuevo']}
        archivos.create.return_value.execute.side_effect = [OSError('timeout simulado'), {'id': 'mes-nuevo'}]
        with self.assertRaises(OSError):
            obtener_directorio(archivos, 'principal', 'DICIEMBRE')
        self.assertEqual(obtener_directorio(archivos, 'principal', 'DICIEMBRE'), 'mes-nuevo')
        self.assertEqual(archivos.generateIds.call_count, 1)
        self.assertEqual([c.kwargs['body']['id'] for c in archivos.create.call_args_list], ['mes-nuevo', 'mes-nuevo'])

    def test_evidencias_meses_cerrados_no_recrean_carpetas(self):
        import evidencia_drive
        solicitud = self.registrar()
        servicio_id = self.servicio()
        with self.sessions() as session:
            session.get(db.Servicio, servicio_id).fecha_registro = datetime(2026, 10, 15, tzinfo=timezone.utc)
            session.add(db.CarpetaEvidencia(servicio_id=servicio_id))
            session.flush()
            session.add(db.FotoEvidencia(servicio_id=servicio_id, posicion=1, formato='jpg', contenido=b'pendiente'))
            session.commit()
        self.autenticar()
        with patch.object(db, 'datetime') as reloj, patch.object(evidencia_drive, 'obtener_drive') as drive:
            reloj.now.return_value = datetime(2026, 11, 25, 15, tzinfo=timezone.utc)
            # Un informe antiguo pendiente no crea ni el mes ni el ticket.
            self.assertTrue(evidencia_drive.sincronizar_evidencia(servicio_id))
            ticket = db.obtener_tickets()[0]
            self.assertTrue(ticket['evidencia_historica'])
            self.assertFalse(ticket['evidencia_pendiente'])
            with patch.object(self.main, 'sincronizar_evidencia', wraps=evidencia_drive.sincronizar_evidencia):
                respuesta = self.client.post(f'/admin/tickets/{solicitud}/evidencia', follow_redirects=False)
                self.assertEqual(respuesta.status_code, 303)
            # Tampoco intenta renombrar una carpeta antigua tras editar el ticket.
            with self.sessions() as session:
                carpeta = session.get(db.CarpetaEvidencia, servicio_id)
                carpeta.carpeta_id = 'carpeta-eliminada'
                carpeta.sincronizada = True
                session.commit()
            db.editar_ticket(solicitud, **self.datos('CORREGIDO'))
            self.assertTrue(evidencia_drive.sincronizar_evidencia(servicio_id))
            drive.assert_not_called()
        with self.sessions() as session:
            self.assertEqual(session.get(db.FotoEvidencia, (servicio_id, 1)).contenido, b'pendiente')

    def test_cierre_mes_respeta_hora_colombia_y_ano(self):
        fecha = datetime(2026, 11, 30, 18, tzinfo=timezone.utc)
        self.assertTrue(db.evidencia_del_mes_actual(fecha, datetime(2026, 12, 1, 4, 59, tzinfo=timezone.utc)))
        self.assertFalse(db.evidencia_del_mes_actual(fecha, datetime(2026, 12, 1, 5, tzinfo=timezone.utc)))
        self.assertFalse(db.evidencia_del_mes_actual(datetime(2025, 11, 25, tzinfo=timezone.utc), fecha))
        self.assertTrue(db.evidencia_del_mes_actual(fecha.replace(tzinfo=None), fecha))

    def test_carpetas_mismo_mes_en_distintos_anos(self):
        from unittest.mock import MagicMock
        from evidencia_drive import obtener_directorio
        archivos = MagicMock()
        archivos.list.return_value.execute.return_value = {'files': []}
        archivos.generateIds.return_value.execute.side_effect = [{'ids':['noviembre-2026']}, {'ids':['noviembre-2027']}]
        self.assertEqual(obtener_directorio(archivos, 'principal', 'NOVIEMBRE', periodo=2026), 'noviembre-2026')
        self.assertEqual(obtener_directorio(archivos, 'principal', 'NOVIEMBRE', periodo=2027), 'noviembre-2027')
        self.assertEqual(archivos.generateIds.call_count, 2)

    def test_cancelar_ticket_realizado_se_rechaza(self):
        solicitud = self.registrar()
        self.servicio()
        self.autenticar()
        self.assertEqual(self.client.post(f"/admin/tickets/{solicitud}/cancelar").status_code, 400)
        self.assertEqual(db.obtener_tickets()[0]["estado"], "REALIZADO")

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
