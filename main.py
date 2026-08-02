from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from database.database import (
    crear_base_datos,
    obtener_tecnicos,
    obtener_tecnico,
    agregar_tecnico,
    editar_tecnico,
    cambiar_estado_tecnico,
    eliminar_tecnico,
    obtener_tecnico_por_credencial
)


import secrets

codigo_admin = None

app = FastAPI()

crear_base_datos()

# Archivos estáticos: imágenes, CSS, etc.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Carpeta donde están los HTML
templates = Jinja2Templates(directory="templates")


@app.get("/")
def inicio(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="tecnico.html"
    )

@app.get("/admin")
def admin_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html"
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
        name="admin_eliminar.html",
        context={
            "tecnico": tecnico
        }
    )

@app.post("/admin/enviar-codigo")
def enviar_codigo_admin(request: Request):

    global codigo_admin

    codigo_admin = str(secrets.randbelow(900000) + 100000)

    print("================================")
    print("CÓDIGO ADMIN:", codigo_admin)
    print("================================")

    return templates.TemplateResponse(
        request=request,
        name="admin_verificar.html"
    )

@app.post("/admin/verificar-codigo")
def verificar_codigo_admin(
    request: Request,
    codigo: str = Form(...)
):

    global codigo_admin

    if codigo == codigo_admin:

        codigo_admin = None

        tecnicos = obtener_tecnicos()

        return templates.TemplateResponse(
            request=request,
            name="admin_panel.html",
            context={
                        "tecnicos": tecnicos
                    }
        )

    
    return templates.TemplateResponse(
        request=request,
        name="admin_verificar.html",
        context={
            "error": "El código ingresado es incorrecto."
        }
    )


@app.get("/admin/panel")
def panel_admin(request: Request):

    tecnicos = obtener_tecnicos()

    return templates.TemplateResponse(
        request=request,
        name="admin_panel.html",
        context={
            "tecnicos": tecnicos
        }
    )

@app.get("/admin/agregar")
def pagina_agregar_tecnico(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="admin_agregar.html"
    )

@app.get("/admin/tecnicos")
def pagina_tecnicos(request: Request):

    tecnicos = obtener_tecnicos()

    return templates.TemplateResponse(
        request=request,
        name="admin_tecnicos.html",
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
        name="admin_editar.html",
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
            name="tecnico.html",
            context={
                "error": "La credencial ingresada no está registrada."
            }
        )

    if tecnico["activo"] == 0:
        return templates.TemplateResponse(
            request=request,
            name="tecnico.html",
            context={
                "error": "Este técnico no se encuentra habilitado."
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="formulario_servicio.html",
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
👷 Técnico: {tecnico["nombre"]}
🪪 Credencial: {tecnico["credencial"]}
🛠️ Perfil: {tecnico["rol"].capitalize()}

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
        name="reporte_generado.html",
        context={
            "mensaje": mensaje
        }
    )


