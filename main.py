import os   
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from auth_codes import crear_codigo, comprobar_codigo, invalidar_codigo
from correo import enviar_codigo
from excel_drive import sincronizar_excel_seguro
from excel_tickets import generar_excel_tickets, NOMBRE_ARCHIVO as NOMBRE_EXCEL_TICKETS
from fastapi.responses import StreamingResponse
from database.database import (
    crear_base_datos,
    obtener_tecnicos,
    obtener_tecnico,
    agregar_tecnico,
    editar_tecnico,
    cambiar_estado_tecnico,
    eliminar_tecnico,
    obtener_tecnico_por_credencial,
    obtener_enlace_externo,
    cancelar_enlace_externo,
    obtener_tienda_por_sap,
    obtener_tiendas,
    agregar_tienda,
    editar_tienda,
    cambiar_estado_tienda,
    crear_servicio_externo,
    eliminar_servicio_prueba,
    anular_servicio_real,
    obtener_tienda_por_id,
    obtener_servicios,
    registrar_ticket,
    obtener_tickets,
    consultar_ticket_servicio,
    asignar_numero_ticket,
    obtener_solicitud_enlace,
    editar_ticket,
    generar_enlace_ticket,
    renovar_enlace_ticket,
    obtener_informe_ticket,
    editar_informe_ticket,
    actualizar_precio_ticket,
    eliminar_ticket
)   


load_dotenv()
codigo_administradores = {}

codigo_tecnicos = {}

# OTP temporal para operadores de servicios externos
codigo_operadores = {}


app = FastAPI()


# ---------------------------------------------------------
# PROTECCIÓN GENERAL DEL PANEL ADMINISTRADOR
# ---------------------------------------------------------

RUTAS_ADMIN_PUBLICAS = {
    "/admin",
    "/admin/enviar-codigo",
    "/admin/verificar-codigo",
}


@app.middleware("http")
async def proteger_rutas_admin(request: Request, call_next):

    ruta = request.url.path

    es_ruta_admin = (
        ruta == "/admin"
        or ruta.startswith("/admin/")
    )

    if not es_ruta_admin:
        return await call_next(request)

    # -----------------------------------------------------
    # RUTAS PÚBLICAS DEL LOGIN ADMIN
    # -----------------------------------------------------

    if ruta in RUTAS_ADMIN_PUBLICAS:
        return await call_next(request)

    # -----------------------------------------------------
    # ADMINISTRADOR
    # -----------------------------------------------------

    # El administrador puede acceder a todas las rutas /admin.
    if request.session.get("admin_autenticado") is True:
        return await call_next(request)

    # -----------------------------------------------------
    # OPERADOR DE SERVICIOS EXTERNOS
    # -----------------------------------------------------

    operador_autenticado = (
        request.session.get("operador_autenticado") is True
        and request.session.get("operador_rol")
        == "operador_servicios_externos"
    )

    if operador_autenticado:

        if not sesion_operador_valida(request):
            return RedirectResponse(url="/tecnico", status_code=303)

        if ruta == "/admin/tickets" or ruta.startswith("/admin/tickets/"):
            if sesion_operador_valida(request):
                return await call_next(request)
            return RedirectResponse(url="/tecnico", status_code=303)

        # El operador únicamente puede entrar a esta sección
        # y a las rutas que cuelgan de ella.
        if (
            ruta == "/admin/servicios-externos"
            or ruta.startswith("/admin/servicios-externos/")
        ):
            return await call_next(request)

        # Si intenta escribir manualmente otra URL /admin,
        # lo devolvemos a su propio panel.
        return RedirectResponse(
            url="/panel-operador",
            status_code=303
        )

    # -----------------------------------------------------
    # SIN AUTENTICACIÓN
    # -----------------------------------------------------

    return RedirectResponse(
        url="/admin",
        status_code=303
    )


# ---------------------------------------------------------
# SESIONES
# ---------------------------------------------------------

SESSION_SECRET = os.getenv("SESSION_SECRET")

if not SESSION_SECRET:
    raise RuntimeError(
        "Falta configurar SESSION_SECRET en el archivo .env"
    )


COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)

if os.getenv("APP_ENV", "development").lower() == "production":
    if not COOKIE_SECURE or len(SESSION_SECRET) < 32:
        raise RuntimeError("Produccion requiere COOKIE_SECURE=true y SESSION_SECRET de al menos 32 caracteres.")


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=COOKIE_SECURE,
    max_age=28800
)


def sesion_operador_valida(request: Request):

    # Debe existir una sesión autenticada
    if not request.session.get("operador_autenticado"):
        return False

    # Debe ser específicamente el operador 400
    credencial = str(request.session.get("operador_credencial", ""))
    if not (credencial == "400" or (credencial.isdigit() and 401 <= int(credencial) <= 499)):
        return False
    if request.session.get("operador_rol") != "operador_servicios_externos":
        return False

    # Obtener fecha y hora de inicio
    inicio = request.session.get("operador_inicio")

    if not inicio:
        return False

    try:
        inicio = datetime.fromisoformat(inicio)
        if inicio.tzinfo is None:
            inicio = inicio.astimezone(timezone.utc)
    except (ValueError, TypeError):
        request.session.clear()
        return False

    # Comprobar si ya pasó una hora
    transcurrido = datetime.now(timezone.utc) - inicio
    if transcurrido < timedelta(0) or transcurrido >= timedelta(hours=1):
        request.session.clear()
        return False

    return True

crear_base_datos()

# Archivos estáticos: imágenes, CSS, etc.
app.mount("/static", StaticFiles(directory="static"), name="static")


# Carpeta donde están los HTML
templates = Jinja2Templates(directory="templates")


@app.exception_handler(ValueError)
async def error_validacion(request: Request, error: ValueError):
    return templates.TemplateResponse(request=request, name="error_validacion.html",
        context={"error": str(error)}, status_code=400)


def admin_autenticado(request: Request):
    return request.session.get("admin_autenticado") is True


# =========================
# GET
# =========================


# =========================
# PORTADA PRINCIPAL
# =========================

@app.get("/")
def inicio(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="inicio.html"
    )


# =========================
# ACCESO TÉCNICOS
# =========================

@app.get("/tecnico")
def acceso_tecnico(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="tecnico/tecnico.html"
    )

@app.get("/admin")
def admin_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin/admin_login.html"
    )


@app.get("/admin/eliminar/{id_tecnico}")
def pagina_eliminar_tecnico(
    request: Request,
    id_tecnico: int
):
    tecnico = obtener_tecnico(id_tecnico)

    if tecnico is None:
        return RedirectResponse(
            url="/admin/tecnicos",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_eliminar.html",
        context={
            "tecnico": tecnico
        }
    )


@app.get("/admin/panel")
def panel_admin(request: Request):

    # Si no inició sesión, devolverlo al login
    if not admin_autenticado(request):
        return RedirectResponse(
            url="/admin",
            status_code=303
        )

    tecnicos = obtener_tecnicos()

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_panel.html",
        context={
            "tecnicos": tecnicos
        }
    )


# ==========================================================
# SERVICIOS EXTERNOS
# ==========================================================

@app.get("/admin/servicios-externos")
def pagina_servicios_externos(request: Request):
    return RedirectResponse(url="/admin/tickets", status_code=303)


@app.get("/admin/servicios")
def pagina_servicios_admin(request: Request):

    servicios = obtener_servicios()

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_servicios.html",
        context={
            "servicios": servicios
        }
    )


@app.get("/admin/tiendas")
def pagina_tiendas_admin(request: Request):

    tiendas = obtener_tiendas()

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_tiendas.html",
        context={
            "tiendas": tiendas
        }
    )


@app.get("/admin/tiendas/agregar")
def pagina_agregar_tienda(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_tienda_agregar.html",
        context={}
    )


@app.post("/admin/tiendas/agregar")
def guardar_nueva_tienda(
    request: Request,
    sap: str = Form(...),
    region: str = Form(""),
    tipo: str = Form(""),
    nombre: str = Form(...),
    ciudad: str = Form(""),
    departamento: str = Form(""),
    direccion: str = Form("")
):

    sap = sap.strip()
    nombre = nombre.strip()

    # SAP obligatorio
    if not sap:
        return templates.TemplateResponse(
            request=request,
            name="admin/admin_tienda_agregar.html",
            context={
                "error": "El SAP de la tienda es obligatorio."
            },
            status_code=400
        )

    # Nombre obligatorio
    if not nombre:
        return templates.TemplateResponse(
            request=request,
            name="admin/admin_tienda_agregar.html",
            context={
                "error": "El nombre de la tienda es obligatorio.",
                "sap": sap
            },
            status_code=400
        )

    # Comprobar si el SAP ya existe
    tienda_existente = obtener_tienda_por_sap(sap)

    if tienda_existente is not None:

        estado = (
            "activa"
            if tienda_existente.activo
            else "inactiva"
        )

        return templates.TemplateResponse(
            request=request,
            name="admin/admin_tienda_agregar.html",
            context={
                "error": (
                    f"El SAP {sap} ya pertenece a "
                    f"{tienda_existente.nombre} y la tienda "
                    f"se encuentra {estado}."
                ),
                "sap": sap,
                "region": region,
                "tipo": tipo,
                "nombre": nombre,
                "ciudad": ciudad,
                "departamento": departamento,
                "direccion": direccion
            },
            status_code=400
        )

    creada = agregar_tienda(
        sap=sap,
        region=region,
        tipo=tipo,
        nombre=nombre,
        ciudad=ciudad,
        departamento=departamento,
        direccion=direccion
    )

    if not creada:
        return templates.TemplateResponse(
            request=request,
            name="admin/admin_tienda_agregar.html",
            context={
                "error": "No fue posible registrar la tienda."
            },
            status_code=400
        )

    return RedirectResponse(
        url="/admin/tiendas",
        status_code=303
    )


# ==========================================================
# VER SERVICIOS - OPERADOR 400
# ==========================================================

@app.get("/operador/servicios")
def pagina_servicios_operador(request: Request):

    if not sesion_operador_valida(request):
        return RedirectResponse(
            url="/",
            status_code=303
        )

    servicios = obtener_servicios()

    return templates.TemplateResponse(
        request=request,
        name="operador/operador_servicios.html",
        context={
            "servicios": servicios
        }
    )

@app.get("/panel-operador")
def panel_operador(request: Request):

    if not sesion_operador_valida(request):
        return RedirectResponse(
            url="/",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="operador/panel_operador.html",
        context={}
    )


# ==========================================================
# ACCESO DEL TÉCNICO EXTERNO
# ==========================================================

@app.get("/s/{token}")
def acceso_servicio_externo(
    request: Request,
    token: str
):

    enlace = obtener_enlace_externo(token)

    # El enlace no existe
    if enlace is None:
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            context={
                "error": "El enlace no existe o no es válido."
            },
            status_code=404
        )

    # El enlace ya fue utilizado o cancelado
    if enlace.estado != "PENDIENTE":
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            context={
                "error": "Este enlace ya no se encuentra disponible."
            },
            status_code=403
        )

    solicitud = obtener_solicitud_enlace(token)
    if solicitud:
        try:
            consultar_ticket_servicio(solicitud["numero"], solicitud["sap"])
        except ValueError as error:
            return templates.TemplateResponse(request=request, name="externo/enlace_invalido.html",
                context={"error": str(error)}, status_code=403)
        return templates.TemplateResponse(request=request, name="externo/formulario.html",
            context={"token": token, "tienda": solicitud["tienda"], "solicitud_vinculada": solicitud,
                     "valores": {"ticket": solicitud["numero"], "ticket_solicitud_id": solicitud["id"]}})
    return templates.TemplateResponse(request=request, name="externo/enlace_invalido.html",
        context={"error": "Solicita a la oficina el enlace asociado a tu ticket."}, status_code=403)


# =========================================================
# EDITAR TIENDA - MOSTRAR FORMULARIO
# =========================================================

@app.get("/admin/tiendas/{id_tienda}/editar")
def pagina_editar_tienda(
    request: Request,
    id_tienda: int
):
    tienda = obtener_tienda_por_id(id_tienda)

    if tienda is None:
        return RedirectResponse(
            url="/admin/tiendas",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_tienda_editar.html",
        context={
            "tienda": tienda
        }
    )




# =========================
# POST
# =========================


@app.post("/admin/enviar-codigo")
def enviar_codigo_admin(request: Request):
    correo = os.getenv("ADMIN_EMAIL")
    if not correo:
        return templates.TemplateResponse(request=request, name="admin/admin_login.html",
            context={"error": "El correo del administrador no esta configurado."}, status_code=503)
    try:
        codigo = crear_codigo(codigo_administradores, "admin")
    except ValueError as error:
        return templates.TemplateResponse(request=request, name="admin/admin_login.html",
            context={"error": str(error)}, status_code=429)
    try:
        enviar_codigo(correo, codigo)
    except Exception:
        invalidar_codigo(codigo_administradores, "admin")
        return templates.TemplateResponse(request=request, name="admin/admin_login.html",
            context={"error": "No fue posible enviar el codigo de verificacion."}, status_code=502)
    return templates.TemplateResponse(request=request, name="admin/admin_verificar.html", context={})


@app.post("/admin/verificar-codigo")
def verificar_codigo_admin(request: Request, codigo: str = Form(...)):
    try:
        comprobar_codigo(codigo_administradores, "admin", codigo)
    except ValueError as error:
        return templates.TemplateResponse(request=request, name="admin/admin_verificar.html",
            context={"error": str(error)}, status_code=400)
    request.session.clear()
    request.session["admin_autenticado"] = True
    return RedirectResponse(url="/admin/panel", status_code=303)


@app.post("/admin/servicios/{servicio_id}/eliminar")
def eliminar_servicio_prueba_admin(
    request: Request,
    servicio_id: int
):
    try:
        eliminar_servicio_prueba(servicio_id)

    except ValueError as e:

        servicios = obtener_servicios()

        return templates.TemplateResponse(
            request=request,
            name="admin/admin_servicios.html",
            context={
                "servicios": servicios,
                "error": str(e)
            },
            status_code=400
        )

    return RedirectResponse(
        url="/admin/servicios",
        status_code=303
    )


@app.post("/admin/servicios/{servicio_id}/anular")
def anular_servicio_real_admin(
    request: Request,
    servicio_id: int
):
    try:
        # Anular primero en PostgreSQL
        anular_servicio_real(servicio_id)

        # Actualizar automáticamente Servicios.xlsx en Google Drive
        # Si Drive falla, la anulación en PostgreSQL se conserva.
        sincronizar_excel_seguro()

    except ValueError as e:

        servicios = obtener_servicios()

        return templates.TemplateResponse(
            request=request,
            name="admin/admin_servicios.html",
            context={
                "servicios": servicios,
                "error": str(e)
            },
            status_code=400
        )

    return RedirectResponse(
        url="/admin/servicios",
        status_code=303
    )



# ==========================================================
# SERVICIOS EXTERNOS
# ==========================================================

@app.post("/admin/cerrar-sesion")
def cerrar_sesion_admin(request: Request):

    request.session.clear()

    return RedirectResponse(
        url="/admin",
        status_code=303
    )


# ==========================================================
# GENERAR ENLACE EXTERNO
# ==========================================================

@app.post("/admin/servicios-externos/generar")
def generar_enlace_externo(request: Request, tipo_registro: str = Form("REAL")):
    return RedirectResponse(url="/admin/tickets", status_code=303)


@app.post("/admin/servicios-externos/cancelar/{id_enlace}")
def cancelar_acceso_externo(id_enlace: int):

    cancelar_enlace_externo(id_enlace)

    return RedirectResponse(
    url="/admin/servicios",
    status_code=303
    )


# ==========================================================
# VERIFICAR TIENDA - SERVICIO EXTERNO
# ==========================================================

@app.post("/s/{token}/verificar-tienda")
def verificar_tienda_externa(request: Request, token: str, sap: str = Form(...)):
    return acceso_servicio_externo(request, token)


# ==========================================================
# GENERAR ENLACE EXTERNO - OPERADOR 400
# ==========================================================

@app.post("/operador/servicios-externos/generar")
def generar_enlace_externo_operador(request: Request, tipo_registro: str = Form("REAL")):
    if not sesion_operador_valida(request):
        return RedirectResponse(url="/tecnico", status_code=303)
    return RedirectResponse(url="/admin/tickets", status_code=303)


@app.post("/s/{token}/formulario")
def formulario_servicio_externo(request: Request, token: str, sap: str = Form(...)):
    return acceso_servicio_externo(request, token)


@app.get("/admin/agregar")
def pagina_agregar_tecnico(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_agregar.html"
    )


@app.get("/admin/tecnicos")
def pagina_tecnicos(request: Request):

    tecnicos = obtener_tecnicos()

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_tecnicos.html",
        context={
            "tecnicos": tecnicos
        }
    )


@app.get("/admin/editar/{id_tecnico}")
def pagina_editar_tecnico(
    request: Request,
    id_tecnico: int
):
    tecnico = obtener_tecnico(id_tecnico)

    if tecnico is None:
        return RedirectResponse(
            url="/admin/tecnicos",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_editar.html",
        context={
            "tecnico": tecnico
        }
    )


@app.post("/admin/editar/{id_tecnico}")
def guardar_edicion_tecnico(
    id_tecnico: int,
    credencial: str = Form(...),
    nombre: str = Form(...),
    correo: str = Form(...),
    rol: str = Form(...)
):
    editar_tecnico(
        id_tecnico=id_tecnico,
        credencial=credencial,
        nombre=nombre,
        correo=correo,
        rol=rol
    )

    return RedirectResponse(
        url="/admin/tecnicos",
        status_code=303
    )


@app.post("/admin/estado/{id_tecnico}")
def estado_tecnico(id_tecnico: int):

    cambiar_estado_tecnico(id_tecnico)

    return RedirectResponse(
        url="/admin/tecnicos",
        status_code=303
    )


@app.post("/admin/agregar-tecnico")
def crear_tecnico(
    credencial: str = Form(...),
    nombre: str = Form(...),
    correo: str = Form(...),
    rol: str = Form(...)
):
    agregar_tecnico(
        credencial=credencial,
        nombre=nombre,
        correo=correo,
        rol=rol
    )

    return RedirectResponse(
        url="/admin/tecnicos",
        status_code=303
    )


@app.post("/admin/eliminar/{id_tecnico}")
def confirmar_eliminar_tecnico(id_tecnico: int):

    eliminar_tecnico(id_tecnico)

    return RedirectResponse(
        url="/admin/tecnicos",
        status_code=303
    )


@app.post("/iniciar-servicio")
def iniciar_servicio(request: Request, credencial: str = Form(...), fecha: str = Form(...)):
    credencial = credencial.strip()
    tecnico = None if credencial == "400" else obtener_tecnico_por_credencial(credencial)
    if credencial != "400" and (tecnico is None or not tecnico.activo):
        return templates.TemplateResponse(request=request, name="tecnico/tecnico.html",
            context={"error": "La credencial no esta registrada o no esta habilitada."}, status_code=400)
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        return templates.TemplateResponse(request=request, name="tecnico/tecnico.html",
            context={"error": "Ingresa una fecha de servicio valida."}, status_code=400)
    operador = credencial == "400" or tecnico.rol == "operador_servicios_externos"
    almacen = codigo_operadores if operador else codigo_tecnicos
    correo = os.getenv("OPERADOR_400_EMAIL") if credencial == "400" else tecnico.correo
    if not correo:
        return templates.TemplateResponse(request=request, name="tecnico/tecnico.html",
            context={"error": "El correo no esta configurado."}, status_code=503)
    try:
        codigo = crear_codigo(almacen, credencial, fecha)
    except ValueError as error:
        return templates.TemplateResponse(request=request, name="tecnico/tecnico.html",
            context={"error": str(error)}, status_code=429)
    try:
        enviar_codigo(correo, codigo)
    except Exception:
        invalidar_codigo(almacen, credencial)
        return templates.TemplateResponse(request=request, name="tecnico/tecnico.html",
            context={"error": "No fue posible enviar el codigo de verificacion."}, status_code=502)
    return templates.TemplateResponse(request=request, name="tecnico/tecnico_verificar.html",
        context={"credencial": credencial, "correo": correo})


@app.post("/verificar-tecnico")
def verificar_tecnico(request: Request, credencial: str = Form(...), codigo: str = Form(...)):
    credencial = credencial.strip()
    tecnico = None if credencial == "400" else obtener_tecnico_por_credencial(credencial)
    if credencial != "400" and (tecnico is None or not tecnico.activo):
        return RedirectResponse(url="/tecnico", status_code=303)
    operador = credencial == "400" or tecnico.rol == "operador_servicios_externos"
    almacen = codigo_operadores if operador else codigo_tecnicos
    try:
        datos = comprobar_codigo(almacen, credencial, codigo)
    except ValueError as error:
        return templates.TemplateResponse(request=request, name="tecnico/tecnico_verificar.html",
            context={"credencial": credencial, "error": str(error)}, status_code=400)
    request.session.clear()
    if operador:
        request.session.update({"operador_autenticado": True,
            "operador_rol": "operador_servicios_externos", "operador_credencial": credencial,
            "operador_inicio": datetime.now(timezone.utc).isoformat()})
        return RedirectResponse(url="/panel-operador", status_code=303)
    request.session.update({"tecnico_id": tecnico.id, "tecnico_fecha": datos["fecha"]})
    return templates.TemplateResponse(request=request, name="formulario/formulario_servicio.html",
        context={"tecnico": tecnico, "fecha": datos["fecha"]})


@app.post("/generar-mensaje")
def generar_mensaje(
    request: Request,
    id_tecnico: int = Form(...),
    fecha: str = Form(...),
    equipo: str = Form(...),
    trabajo_realizado: str = Form(...),
    observaciones: str = Form(""),
    recomendaciones: str = Form("")
):
    if request.session.get("tecnico_id") != id_tecnico or request.session.get("tecnico_fecha") != fecha:
        return RedirectResponse(url="/tecnico", status_code=303)
    tecnico = obtener_tecnico(id_tecnico)

    if tecnico is None or not tecnico.activo:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    if not equipo.strip() or len(trabajo_realizado.split()) < 25:
        return templates.TemplateResponse(request=request, name="formulario/formulario_servicio.html",
            context={"tecnico": tecnico, "fecha": fecha,
                     "error": "Completa el equipo y escribe al menos 25 palabras en Trabajo realizado."}, status_code=400)

    mensaje = f"""🏢 BS ELECTROMECÁNICA S.A.S.
📋 INFORME DE SERVICIO

📅 Fecha: {fecha}
👷 Técnico: {tecnico.nombre}
🪪 Credencial: {tecnico.credencial}
🛠️ Perfil: {tecnico.rol.capitalize()}

⚙️ EQUIPO
{equipo}

🔧 TRABAJO REALIZADO
{trabajo_realizado}

🔎 OBSERVACIONES
{observaciones if observaciones else "Sin observaciones."}

💡 RECOMENDACIONES
{recomendaciones if recomendaciones else "Sin recomendaciones."}

Muchas gracias por leer.
"""

    return templates.TemplateResponse(
        request=request,
        name="formulario/reporte_generado.html",
        context={
            "mensaje": mensaje
        }
    )


@app.post("/s/{token}/guardar-servicio")
def guardar_servicio_externo(

    request: Request,
    token: str,

    sap_tienda: str = Form(...),

    ticket: str = Form(...),
    tipo_servicio: str = Form(...),
    otro_tipo_servicio: str = Form(""),

    cedula_tecnico: str = Form(...),
    nombre_tecnico: str = Form(...),
    telefono_tecnico: str = Form(...),

    sap_encargado: str = Form(...),
    nombre_encargado: str = Form(...),

    descripcion_falla: str = Form(...),
    trabajo_realizado: str = Form(...),

    observaciones: str = Form(""),

    suministro_repuestos: str = Form(...),
    repuestos_suministrados: str = Form(""),
    ticket_solicitud_id: int | None = Form(None)
):

    valores = {k: v for k, v in locals().items() if k not in ("request", "token")}

    # ==========================================================
    # 1. VERIFICAR EL ENLACE
    # ==========================================================

    enlace = obtener_enlace_externo(token)

    if enlace is None:
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            context={
                "error": "El enlace no existe o no es válido."
            },
            status_code=404
        )

    if enlace.estado != "PENDIENTE":
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            context={
                "error": "Este enlace ya no se encuentra disponible."
            },
            status_code=403
        )

    # ==========================================================
    # 3. TIPO DE SERVICIO
    # ==========================================================

    if tipo_servicio == "OTRO":

        otro_tipo_servicio = otro_tipo_servicio.strip()

        if not otro_tipo_servicio:
            return templates.TemplateResponse(
                request=request,
                name="externo/formulario.html",
                context={
                    "error": "Debes indicar cuál es el tipo de servicio.",
                    "token": token,
                    "tienda": obtener_tienda_por_sap(sap_tienda),
                    "valores": valores,
                    "solicitud_vinculada": obtener_solicitud_enlace(token)
                },
                status_code=400
            )

        tipo_servicio = otro_tipo_servicio

    # ==========================================================
    # 4. GUARDAR SERVICIO EN POSTGRESQL
    # ==========================================================

    try:

        servicio_id = crear_servicio_externo(
            token=token,
            sap_tienda=sap_tienda,

            ticket=ticket,
            tipo_servicio=tipo_servicio,

            cedula_tecnico=cedula_tecnico,
            nombre_tecnico=nombre_tecnico,
            telefono_tecnico=telefono_tecnico,

            sap_encargado=sap_encargado,
            nombre_encargado=nombre_encargado,

            descripcion_falla=descripcion_falla,
            trabajo_realizado=trabajo_realizado,

            observaciones=observaciones,

            suministro_repuestos=suministro_repuestos,
            repuestos_suministrados=repuestos_suministrados,

            tipo_registro=enlace.tipo_registro,
            ticket_solicitud_id=ticket_solicitud_id
        )

        # ======================================================
        # 5. SINCRONIZAR EXCEL CON GOOGLE DRIVE
        # ======================================================
        # PostgreSQL ya guardó el servicio.
        # Si Google Drive falla, el servicio NO se pierde.

        sincronizar_excel_seguro()

        # ======================================================
        # 6. MOSTRAR CONFIRMACIÓN
        # ======================================================

        return templates.TemplateResponse(
            request=request,
            name="externo/servicio_guardado.html",
            context={
                "servicio_id": servicio_id,
                "enlace_id": enlace.id
            }
        )

    except ValueError as error:

        return templates.TemplateResponse(
            request=request,
            name="externo/formulario.html",
            context={
                "error": str(error),
                "token": token,
                "tienda": obtener_tienda_por_sap(sap_tienda),
                "valores": valores,
                "solicitud_vinculada": obtener_solicitud_enlace(token)
            },
            status_code=400
        )



# =========================================================
# EDITAR TIENDA - GUARDAR CAMBIOS
# =========================================================

@app.post("/admin/tiendas/{id_tienda}/editar")
def guardar_edicion_tienda(
    request: Request,
    id_tienda: int,
    region: str = Form(...),
    tipo: str = Form(""),
    nombre: str = Form(...),
    ciudad: str = Form(""),
    departamento: str = Form(""),
    direccion: str = Form("")
):
    tienda = obtener_tienda_por_id(id_tienda)

    if tienda is None:
        return RedirectResponse(
            url="/admin/tiendas",
            status_code=303
        )

    nombre = nombre.strip()
    region = region.strip()

    if not nombre:
        return templates.TemplateResponse(
            request=request,
            name="admin/admin_tienda_editar.html",
            context={
                "tienda": tienda,
                "error": "El nombre de la tienda es obligatorio."
            },
            status_code=400
        )

    if region not in ["1", "7", "8"]:
        return templates.TemplateResponse(
            request=request,
            name="admin/admin_tienda_editar.html",
            context={
                "tienda": tienda,
                "error": "La región seleccionada no es válida."
            },
            status_code=400
        )

    resultado = editar_tienda(
        id_tienda=id_tienda,
        region=region,
        tipo=tipo,
        nombre=nombre,
        ciudad=ciudad,
        departamento=departamento,
        direccion=direccion
    )

    if not resultado:
        return templates.TemplateResponse(
            request=request,
            name="admin/admin_tienda_editar.html",
            context={
                "tienda": tienda,
                "error": "No fue posible actualizar la tienda."
            },
            status_code=400
        )

    return RedirectResponse(
        url="/admin/tiendas",
        status_code=303
    )


# =========================================================
# ACTIVAR / DESACTIVAR TIENDA
# =========================================================

@app.post("/admin/tiendas/{id_tienda}/estado")
def cambiar_estado_tienda_admin(
    id_tienda: int,
    activo: bool = Form(...)
):
    cambiar_estado_tienda(
        id_tienda,
        activo
    )

    return RedirectResponse(
        url="/admin/tiendas",
        status_code=303
    )


# Registro de solicitudes de la oficina; protegido por el middleware /admin.
def pagina_tickets(request, error=None, valores=None, status_code=200, editar_id=None):
    tickets = obtener_tickets()
    filtros = {
        "todos": ("Todas las solicitudes", lambda t: True),
        "pendientes": ("Solicitudes pendientes", lambda t: t["estado"] == "PENDIENTE"),
        "realizados": ("Servicios realizados", lambda t: t["estado"] == "REALIZADO"),
        "sin-numero": ("Solicitudes sin número de ticket", lambda t: t["numero"] == "000"),
        "sin-precio": ("Solicitudes faltantes de precio", lambda t: t["precio"] is None),
    }
    filtro = request.query_params.get("filtro", "todos")
    if filtro not in filtros:
        filtro = "todos"
    titulo, coincide = filtros[filtro]
    return templates.TemplateResponse(
        request=request, name="admin/admin_tickets.html",
        context={"tickets": tickets, "error": error, "valores": valores or {}, "editar_id": editar_id,
                 "tickets_visibles": [t for t in tickets if coincide(t)],
                 "filtro_activo": filtro, "titulo_listado": titulo,
                 "pendientes": sum(t["estado"] == "PENDIENTE" for t in tickets),
                 "realizados": sum(t["estado"] == "REALIZADO" for t in tickets),
                 "sin_numero": sum(t["numero"] == "000" for t in tickets)},
        status_code=status_code
    )


@app.get("/admin/tickets")
def listar_tickets(request: Request):
    return pagina_tickets(request)


@app.get("/admin/tickets/tienda")
def consultar_tienda_ticket(sap: str):
    tienda = obtener_tienda_por_sap(sap)
    if tienda is None or not tienda.activo:
        return JSONResponse({"error": "No existe una tienda activa con ese SAP."}, status_code=404)
    return {"sap": tienda.sap, "nombre": tienda.nombre,
            "direccion": tienda.direccion or "", "ciudad": tienda.ciudad or ""}


@app.post("/admin/tickets")
def crear_ticket_oficina(
    request: Request, numero: str = Form(...), sap_tienda: str = Form(...),
    prioridad: str = Form(...), fecha_reporte: str = Form(...),
    equipo: str = Form(...), descripcion: str = Form(...),
    contacto: str = Form(""), telefonos: str = Form(""),
    registrado_por: str = Form(""), coordinador: str = Form(""), codigo: str = Form("")
):
    valores = {k: v for k, v in locals().items() if k != "request"}
    try:
        registrar_ticket(**valores)
    except ValueError as error:
        return pagina_tickets(request, str(error), valores, 400)
    sincronizar_excel_seguro()
    return RedirectResponse("/admin/tickets", status_code=303)


@app.post("/admin/tickets/{solicitud_id}/numero")
def completar_numero_ticket(request: Request, solicitud_id: int, numero: str = Form(...)):
    try:
        asignar_numero_ticket(solicitud_id, numero)
    except ValueError as error:
        return pagina_tickets(request, str(error), status_code=400)
    sincronizar_excel_seguro()
    return RedirectResponse("/admin/tickets", status_code=303)


@app.get("/s/{token}/verificar-ticket")
def verificar_ticket_externo(token: str, numero: str, sap: str):
    enlace = obtener_enlace_externo(token)
    if enlace is None or enlace.estado != "PENDIENTE":
        return JSONResponse({"error": "Este enlace ya no está disponible."}, status_code=403)
    try:
        solicitud = obtener_solicitud_enlace(token)
        if solicitud and (solicitud["numero"] != numero.strip().upper() or solicitud["sap"] != sap.strip()):
            raise ValueError("Los datos del ticket cambiaron o no corresponden al enlace. Vuelve a abrir el enlace.")
        solicitudes = consultar_ticket_servicio(numero, sap)
        if solicitud:
            solicitudes = [s for s in solicitudes if s["id"] == solicitud["id"]]
            if not solicitudes:
                raise ValueError("Esta solicitud ya no está pendiente.")
        return {"solicitudes": solicitudes}
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)


@app.get("/admin/tickets/{solicitud_id}/editar")
def pagina_editar_ticket(request: Request, solicitud_id: int):
    ticket = next((t for t in obtener_tickets() if t["id"] == solicitud_id), None)
    if ticket is None:
        return pagina_tickets(request, "La solicitud no existe.", status_code=404)
    valores = dict(ticket, sap_tienda=ticket["sap"], fecha_reporte=ticket["fecha_reporte"].isoformat())
    return pagina_tickets(request, valores=valores, editar_id=solicitud_id)


@app.post("/admin/tickets/{solicitud_id}/editar")
def guardar_edicion_ticket(
    request: Request, solicitud_id: int, numero: str = Form(...), sap_tienda: str = Form(...),
    prioridad: str = Form(...), fecha_reporte: str = Form(...), equipo: str = Form(...),
    descripcion: str = Form(...), contacto: str = Form(""), telefonos: str = Form(""),
    registrado_por: str = Form(""), coordinador: str = Form(""), codigo: str = Form("")
):
    valores = {k: v for k, v in locals().items() if k not in ("request", "solicitud_id")}
    try:
        editar_ticket(solicitud_id, **valores)
    except ValueError as error:
        return pagina_tickets(request, str(error), valores, 400, editar_id=solicitud_id)
    sincronizar_excel_seguro()
    return RedirectResponse("/admin/tickets", status_code=303)


@app.post("/admin/tickets/{solicitud_id}/enlace")
def crear_enlace_solicitud_anterior(request: Request, solicitud_id: int):
    try:
        generar_enlace_ticket(solicitud_id)
    except ValueError as error:
        return pagina_tickets(request, str(error), status_code=400)
    return RedirectResponse("/admin/tickets", status_code=303)


def mostrar_edicion_informe(request, solicitud_id, valores, error=None, status_code=200):
    return templates.TemplateResponse(request=request, name="admin/admin_informe_editar.html",
        context={"solicitud_id": solicitud_id, "valores": valores, "error": error}, status_code=status_code)


@app.get("/admin/tickets/{solicitud_id}/informe/editar")
def pagina_editar_informe(request: Request, solicitud_id: int):
    try:
        valores = obtener_informe_ticket(solicitud_id)
    except ValueError as error:
        return pagina_tickets(request, str(error), status_code=404)
    return mostrar_edicion_informe(request, solicitud_id, valores)


@app.post("/admin/tickets/{solicitud_id}/informe/editar")
def guardar_edicion_informe(
    request: Request, solicitud_id: int, cedula_tecnico: str = Form(...),
    nombre_tecnico: str = Form(...), telefono_tecnico: str = Form(...),
    tipo_servicio: str = Form(...), sap_encargado: str = Form(...),
    nombre_encargado: str = Form(...), descripcion_falla: str = Form(...),
    trabajo_realizado: str = Form(...), observaciones: str = Form(""),
    suministro_repuestos: str = Form(...), repuestos_suministrados: str = Form("")
):
    valores = {k: v for k, v in locals().items() if k not in ("request", "solicitud_id")}
    try:
        editar_informe_ticket(solicitud_id, **valores)
    except ValueError as error:
        return mostrar_edicion_informe(request, solicitud_id, valores, str(error), 400)
    sincronizar_excel_seguro()
    return RedirectResponse(f"/admin/tickets#solicitud-{solicitud_id}", status_code=303)


@app.post("/admin/tickets/{solicitud_id}/renovar-enlace")
def reemplazar_enlace_ticket(request: Request, solicitud_id: int):
    try:
        renovar_enlace_ticket(solicitud_id)
    except ValueError as error:
        return pagina_tickets(request, str(error), status_code=400)
    return RedirectResponse(f"/admin/tickets#solicitud-{solicitud_id}", status_code=303)


@app.post("/admin/tickets/{solicitud_id}/precio")
def guardar_precio_ticket(request: Request, solicitud_id: int, precio: str = Form(...)):
    try:
        actualizar_precio_ticket(solicitud_id, precio)
    except ValueError as error:
        return pagina_tickets(request, str(error), status_code=400)
    sincronizar_excel_seguro()
    return RedirectResponse("/admin/tickets", status_code=303)


@app.post("/admin/tickets/{solicitud_id}/eliminar")
def borrar_ticket(request: Request, solicitud_id: int):
    try:
        eliminar_ticket(solicitud_id)
    except ValueError as error:
        return pagina_tickets(request, str(error), status_code=400)
    sincronizar_excel_seguro()
    return RedirectResponse("/admin/tickets", status_code=303)


@app.get("/admin/tickets/excel")
def descargar_excel_tickets(request: Request):
    return StreamingResponse(
        generar_excel_tickets(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{NOMBRE_EXCEL_TICKETS}"',
            "Cache-Control": "no-store",
        },
    )
