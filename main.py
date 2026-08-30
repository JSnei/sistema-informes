import os   
import secrets
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from correo import enviar_codigo
from database.database import (
    crear_base_datos,
    obtener_tecnicos,
    obtener_tecnico,
    agregar_tecnico,
    editar_tecnico,
    cambiar_estado_tecnico,
    eliminar_tecnico,
    obtener_tecnico_por_credencial,
    crear_enlace_externo,
    obtener_enlace_externo,
    obtener_enlaces_externos,
    cancelar_enlace_externo,
    obtener_tienda_por_sap,
    crear_servicio_externo,
    eliminar_servicio_prueba,
    anular_servicio_real,
    obtener_servicios
)


load_dotenv()
codigo_admin = {
    "codigo": None,
    "expira": None,
    "ultimo_envio": None,
    "intentos": 0
}
codigo_tecnicos = {}


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

    if es_ruta_admin and ruta not in RUTAS_ADMIN_PUBLICAS:

        if request.session.get("admin_autenticado") is not True:

            return RedirectResponse(
                url="/admin",
                status_code=303
            )

    return await call_next(request)


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


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=COOKIE_SECURE,
    max_age=28800
)


crear_base_datos()

# Archivos estáticos: imágenes, CSS, etc.
app.mount("/static", StaticFiles(directory="static"), name="static")


# Carpeta donde están los HTML
templates = Jinja2Templates(directory="templates")


def admin_autenticado(request: Request):
    return request.session.get("admin_autenticado") is True


def enlace_externo_vencido(enlace):
    """
    Un enlace externo tiene una vigencia máxima de 24 horas.
    Devuelve True si ya venció.
    """

    if enlace.fecha_creacion is None:
        return True

    fecha_creacion = enlace.fecha_creacion

    # PostgreSQL puede devolver la fecha sin zona horaria.
    # En ese caso asumimos UTC.
    if fecha_creacion.tzinfo is None:
        fecha_creacion = fecha_creacion.replace(tzinfo=timezone.utc)

    ahora = datetime.now(timezone.utc)

    return ahora > fecha_creacion + timedelta(hours=24)


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

    enlaces = obtener_enlaces_externos()

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_servicios_externos.html",
        context={
            "enlaces": enlaces
        }
    )


# ==========================================================
# SERVICIOS REGISTRADOS - ADMIN
# ==========================================================

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

# =========================
# POST
# =========================


@app.post("/admin/enviar-codigo")
def enviar_codigo_admin(request: Request):

    global codigo_admin

    ahora = datetime.now(timezone.utc)

    # Evitar que se soliciten códigos demasiado rápido
    if codigo_admin["ultimo_envio"] is not None:

        tiempo_transcurrido = (
            ahora - codigo_admin["ultimo_envio"]
        ).total_seconds()

        if tiempo_transcurrido < 60:

            segundos_restantes = int(
                60 - tiempo_transcurrido
            )

            return templates.TemplateResponse(
                request=request,
                name="admin/admin_login.html",
                context={
                    "error":
                    f"Espera {segundos_restantes} segundos "
                    "antes de solicitar otro código."
                }
            )

    # Generar código OTP de 6 dígitos
    codigo = str(
        secrets.randbelow(900000) + 100000
    )

    correo_admin = os.getenv("ADMIN_EMAIL")

    if not correo_admin:
        raise RuntimeError(
            "Falta configurar ADMIN_EMAIL en el archivo .env"
        )

    # Enviar código por correo
    try:

        enviar_codigo(
            correo_admin,
            codigo
        )

        print("Código de administrador enviado correctamente.")

    except Exception as error:

        print(
            "ERROR AL ENVIAR CÓDIGO ADMIN:",
            error
        )

        return templates.TemplateResponse(
            request=request,
            name="admin/admin_login.html",
            context={
                "error":
                "No fue posible enviar el código de verificación."
            }
        )

    # Guardar información temporal del OTP
    codigo_admin["codigo"] = codigo
    codigo_admin["expira"] = ahora + timedelta(minutes=10)
    codigo_admin["ultimo_envio"] = ahora
    codigo_admin["intentos"] = 0

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_verificar.html",
        context={}
    )


@app.post("/admin/verificar-codigo")
def verificar_codigo_admin(
    request: Request,
    codigo: str = Form(...)
):

    global codigo_admin

    ahora = datetime.now(timezone.utc)

    # ==========================================
    # COMPROBAR QUE EXISTA UN CÓDIGO ACTIVO
    # ==========================================

    if codigo_admin["codigo"] is None:

        return templates.TemplateResponse(
            request=request,
            name="admin/admin_login.html",
            context={
                "error":
                "No hay un código activo. Solicita uno nuevo."
            }
        )

    # ==========================================
    # COMPROBAR SI EL CÓDIGO VENCIÓ
    # ==========================================

    if (
        codigo_admin["expira"] is None
        or ahora > codigo_admin["expira"]
    ):

        codigo_admin["codigo"] = None
        codigo_admin["expira"] = None
        codigo_admin["intentos"] = 0

        return templates.TemplateResponse(
            request=request,
            name="admin/admin_login.html",
            context={
                "error":
                "El código venció. Solicita uno nuevo."
            }
        )

    # ==========================================
    # COMPROBAR SI EL CÓDIGO ES CORRECTO
    # ==========================================

    if secrets.compare_digest(
        codigo.strip(),
        codigo_admin["codigo"]
    ):

        # Invalidar OTP después de utilizarlo
        codigo_admin["codigo"] = None
        codigo_admin["expira"] = None
        codigo_admin["intentos"] = 0

        # Crear sesión del administrador
        request.session["admin_autenticado"] = True

        return RedirectResponse(
            url="/admin/panel",
            status_code=303
        )

    # ==========================================
    # CÓDIGO INCORRECTO
    # ==========================================

    codigo_admin["intentos"] += 1

    # Al quinto intento incorrecto,
    # invalidar completamente el OTP
    if codigo_admin["intentos"] >= 5:

        codigo_admin["codigo"] = None
        codigo_admin["expira"] = None
        codigo_admin["intentos"] = 0

        return templates.TemplateResponse(
            request=request,
            name="admin/admin_login.html",
            context={
                "error":
                "Se superó el número máximo de intentos. "
                "Solicita un nuevo código."
            }
        )

    # ==========================================
    # MOSTRAR INTENTOS RESTANTES
    # ==========================================

    intentos_restantes = (
        5 - codigo_admin["intentos"]
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_verificar.html",
        context={
            "error":
            f"Código incorrecto. "
            f"Te quedan {intentos_restantes} intentos."
        }
    )

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
        anular_servicio_real(servicio_id)

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
def generar_enlace_externo(
    request: Request,
    tipo_registro: str = Form("REAL")
):
    tipo_registro = str(tipo_registro).strip().upper()

    # Seguridad: no confiar en lo que venga del navegador
    if tipo_registro not in ["REAL", "PRUEBA"]:
        enlaces = obtener_enlaces_externos()

        return templates.TemplateResponse(
            request=request,
            name="admin/admin_servicios_externos.html",
            context={
                "enlaces": enlaces,
                "error": "El tipo de registro seleccionado no es válido."
            },
            status_code=400
        )

    token = secrets.token_urlsafe(32)

    crear_enlace_externo(
        token,
        tipo_registro
    )

    enlace_completo = str(
        request.url_for(
            "acceso_servicio_externo",
            token=token
        )
    )

    enlaces = obtener_enlaces_externos()

    return templates.TemplateResponse(
        request=request,
        name="admin/admin_servicios_externos.html",
        context={
            "enlaces": enlaces,
            "enlace_generado": enlace_completo
        }
    )

# ==========================================================
# CANCELAR ENLACE EXTERNO
# ==========================================================

@app.post("/admin/servicios-externos/cancelar/{id_enlace}")
def cancelar_acceso_externo(id_enlace: int):

    cancelar_enlace_externo(id_enlace)

    return RedirectResponse(
    url="/admin/servicios",
    status_code=303
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

    # El enlace superó las 24 horas
    if enlace_externo_vencido(enlace):
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            context={
                "error": "Este enlace ha vencido. Solicita uno nuevo."
            },
            status_code=403
        )

    return templates.TemplateResponse(
        request=request,
        name="externo/acceso.html",
        context={
            "token": token
        }
    )

# ==========================================================
# VERIFICAR TIENDA - SERVICIO EXTERNO
# ==========================================================

@app.post("/s/{token}/verificar-tienda")
def verificar_tienda_externa(
    request: Request,
    token: str,
    sap: str = Form(...)
    ):

    # Primero verificamos que el enlace exista
    enlace = obtener_enlace_externo(token)

    if enlace is None:
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            status_code=404
        )

    # Verificamos que el enlace siga disponible
    if enlace.estado != "PENDIENTE":
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            status_code=403
        )

    # Verificar que el enlace no haya superado las 24 horas
    if enlace_externo_vencido(enlace):
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            context={
                "error": "Este enlace ha vencido. Solicita uno nuevo."
            },
            status_code=403
        )

    # Limpiamos el SAP ingresado
    sap = sap.strip()

    # Consultamos PostgreSQL
    tienda = obtener_tienda_por_sap(sap)

    # Si la tienda no existe
    if tienda is None:
        return templates.TemplateResponse(
            request=request,
            name="externo/acceso.html",
            context={
                "token": token,
                "sap_ingresado": sap,
                "error": "La tienda ingresada no está registrada en el sistema."
            }
        )

    # Si está desactivada
    if not tienda.activo:
        return templates.TemplateResponse(
            request=request,
            name="externo/acceso.html",
            context={
                "token": token,
                "sap_ingresado": sap,
                "error": "Esta tienda se encuentra deshabilitada."
            }
        )

    # Tienda encontrada
    return templates.TemplateResponse(
        request=request,
        name="externo/acceso.html",
        context={
            "token": token,
            "tienda": tienda
        }
    )


# ==========================================================
# FORMULARIO DE SERVICIO EXTERNO
# ==========================================================

@app.post("/s/{token}/formulario")
def formulario_servicio_externo(
    request: Request,
    token: str,
    sap: str = Form(...)
    ):

    # Verificar nuevamente el enlace
    enlace = obtener_enlace_externo(token)

    if enlace is None:
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            status_code=404
        )

    if enlace.estado != "PENDIENTE":
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            status_code=403
        )

    # Verificar que el enlace no haya superado las 24 horas
    if enlace_externo_vencido(enlace):
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            context={
                "error": "Este enlace ha vencido. Solicita uno nuevo."
            },
            status_code=403
        )

    # IMPORTANTE:
    # No confiamos solamente en el SAP enviado por el navegador.
    # Volvemos a comprobarlo en PostgreSQL.
    tienda = obtener_tienda_por_sap(sap)

    if tienda is None or not tienda.activo:
        return RedirectResponse(
            url=f"/s/{token}",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="externo/formulario.html",
        context={
            "token": token,
            "tienda": tienda
        }
    )


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
def iniciar_servicio(
    request: Request,
    credencial: str = Form(...),
    fecha: str = Form(...)
):
    tecnico = obtener_tecnico_por_credencial(credencial)

    if tecnico is None:
        return templates.TemplateResponse(
            request=request,
            name="tecnico/tecnico.html",
            context={
                "error": "La credencial ingresada no está registrada."
            }
        )

    if tecnico.activo == 0:
        return templates.TemplateResponse(
            request=request,
            name="tecnico/tecnico.html",
            context={
                "error": "Este técnico no se encuentra habilitado."
            }
        )

    # Generar código aleatorio de 6 dígitos
    codigo = str(secrets.randbelow(900000) + 100000)

    # Guardamos temporalmente la información del acceso
    codigo_tecnicos[credencial] = {
        "codigo": codigo,
        "fecha": fecha
    }

    # Enviar el código al correo registrado del técnico
    try:
        enviar_codigo(
            tecnico.correo,
            codigo
        )
    except Exception as error:
        print("ERROR AL ENVIAR CORREO:", error)

        return templates.TemplateResponse(
            request=request,
            name="tecnico/tecnico.html",
            context={
                "error": "No fue posible enviar el código de verificación."
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="tecnico/tecnico_verificar.html",
        context={
            "credencial": credencial,
            "correo": tecnico.correo
        }
    )


@app.post("/verificar-tecnico")
def verificar_tecnico(
    request: Request,
    credencial: str = Form(...),
    codigo: str = Form(...)
):
    tecnico = obtener_tecnico_por_credencial(credencial)

    if tecnico is None:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    datos = codigo_tecnicos.get(credencial)

    if datos is None:
        return RedirectResponse(
            url="/",
            status_code=303
        )

    if codigo != datos["codigo"]:
        return templates.TemplateResponse(
            request=request,
            name="tecnico/tecnico_verificar.html",
            context={
                "credencial": credencial,
                "correo": tecnico.correo,
                "error": "El código ingresado es incorrecto."
            }
        )

    fecha = datos["fecha"]

    # El código solo puede utilizarse una vez
    del codigo_tecnicos[credencial]

    return templates.TemplateResponse(
        request=request,
        name="formulario/formulario_servicio.html",
        context={
            "tecnico": tecnico,
            "fecha": fecha
        }
    )


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
    tecnico = obtener_tecnico(id_tecnico)

    if tecnico is None:
        return RedirectResponse(
            url="/",
            status_code=303
        )

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

    cedula_tecnico: str = Form(...),
    nombre_tecnico: str = Form(...),

    sap_encargado: str = Form(...),
    nombre_encargado: str = Form(...),

    descripcion_falla: str = Form(...),
    trabajo_realizado: str = Form(...),

    observaciones: str = Form(""),

    suministro_repuestos: str = Form(...),
    repuestos_suministrados: str = Form("")
):

    # Verificar el enlace antes de guardar
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

    # Impedir guardar servicios con enlaces de más de 24 horas
    if enlace_externo_vencido(enlace):
        return templates.TemplateResponse(
            request=request,
            name="externo/enlace_invalido.html",
            context={
                "error": "Este enlace ha vencido. Solicita uno nuevo."
            },
            status_code=403
        )

    try:

        servicio_id = crear_servicio_externo(
            token=token,
            sap_tienda=sap_tienda,

            ticket=ticket,
            tipo_servicio=tipo_servicio,

            cedula_tecnico=cedula_tecnico,
            nombre_tecnico=nombre_tecnico,

            sap_encargado=sap_encargado,
            nombre_encargado=nombre_encargado,

            descripcion_falla=descripcion_falla,
            trabajo_realizado=trabajo_realizado,

            observaciones=observaciones,

            suministro_repuestos=suministro_repuestos,
            repuestos_suministrados=repuestos_suministrados,

            tipo_registro=enlace.tipo_registro
        )

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
            name="externo/enlace_invalido.html",
            context={
                "error": str(error)
            },
            status_code=400
        )