import os
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from database.database import obtener_servicios_para_excel
from excel_tickets import generar_excel_tickets, NOMBRE_ARCHIVO as NOMBRE_TICKETS


# ==========================================================
# CONFIGURACIÓN GOOGLE DRIVE
# ==========================================================

GOOGLE_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_DRIVE_CREDENTIALS",
    "/home/bsadmin/google-drive-credentials.json"
)

GOOGLE_DRIVE_FOLDER_ID = os.getenv(
    "GOOGLE_DRIVE_FOLDER_ID"
)

GOOGLE_DRIVE_OAUTH_TOKEN = os.getenv("GOOGLE_DRIVE_OAUTH_TOKEN")
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

NOMBRE_ARCHIVO = "Servicios.xlsx"


# ==========================================================
# GENERAR EXCEL DESDE POSTGRESQL
# ==========================================================

def generar_excel_servicios():

    servicios = obtener_servicios_para_excel()

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Servicios"

    encabezados = [
        "N° Servicio",
        "N° Solicitud",
        "Fecha",
        "Ticket",
        "SAP Tienda",
        "Nombre Tienda",
        "Ciudad",
        "Departamento",
        "Dirección",
        "Región",
        "Tipo Tienda",
        "Tipo Servicio",
        "Cédula Técnico",
        "Nombre Técnico",
        "SAP Encargado",
        "Nombre Encargado",
        "Descripción Falla",
        "Trabajo Realizado",
        "Observaciones",
        "¿Suministró Repuestos?",
        "Repuestos Suministrados",
        "Estado",
        "Teléfono Técnico",
    ]

    hoja.append(encabezados)

    for celda in hoja[1]:
        celda.font = Font(bold=True)
        celda.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

    for servicio in servicios:

        hoja.append([
            servicio["servicio_id"],
            servicio["solicitud_id"],
            servicio["fecha"].replace(tzinfo=None) if servicio["fecha"] else None,
            servicio["ticket"],
            servicio["sap_tienda"],
            servicio["nombre_tienda"],
            servicio["ciudad"],
            servicio["departamento"],
            servicio["direccion"],
            servicio["region"],
            servicio["tipo_tienda"],
            servicio["tipo_servicio"],
            servicio["cedula_tecnico"],
            servicio["nombre_tecnico"],
            servicio["sap_encargado"],
            servicio["nombre_encargado"],
            servicio["descripcion_falla"],
            servicio["trabajo_realizado"],
            servicio["observaciones"],
            servicio["suministro_repuestos"],
            servicio["repuestos_suministrados"],
            servicio["estado"],
            servicio["telefono_tecnico"],
        ])
        for celda in hoja[hoja.max_row]:
            if isinstance(celda.value, str):
                celda.data_type = "s"

    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions

    for columna in range(1, hoja.max_column + 1):

        letra = get_column_letter(columna)
        ancho_maximo = 0

        for celda in hoja[letra]:

            if celda.value is not None:
                ancho_maximo = max(
                    ancho_maximo,
                    len(str(celda.value))
                )

        hoja.column_dimensions[letra].width = min(
            ancho_maximo + 2,
            45
        )

    archivo = BytesIO()
    libro.save(archivo)
    archivo.seek(0)

    return archivo


# ==========================================================
# CONECTAR CON GOOGLE DRIVE
# ==========================================================

def obtener_drive():

    if not GOOGLE_DRIVE_FOLDER_ID:
        raise RuntimeError(
            "GOOGLE_DRIVE_FOLDER_ID no está configurado."
        )

    if GOOGLE_DRIVE_OAUTH_TOKEN:
        credenciales = UserCredentials.from_authorized_user_file(
            GOOGLE_DRIVE_OAUTH_TOKEN, scopes=DRIVE_SCOPES)
        if not credenciales.refresh_token:
            raise RuntimeError("Autoriza nuevamente Google Drive para permitir el acceso sin sesión abierta.")
    else:
        credenciales = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=DRIVE_SCOPES)

    return build(
        "drive",
        "v3",
        credentials=credenciales,
        cache_discovery=False
    )


# ==========================================================
# SUBIR O ACTUALIZAR SERVICIOS.XLSX
# ==========================================================

def sincronizar_excel_drive(nombre_archivo=NOMBRE_ARCHIVO, generador=generar_excel_servicios):

    drive = obtener_drive()
    archivo = generador()

    media = MediaIoBaseUpload(
        archivo,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        resumable=False
    )

    consulta = (
        f"name='{nombre_archivo}' "
        f"and '{GOOGLE_DRIVE_FOLDER_ID}' in parents "
        "and trashed=false"
    )

    resultado = drive.files().list(
        q=consulta,
        fields="files(id, name)"
    ).execute()

    archivos = resultado.get("files", [])

    # Si ya existe, reemplazamos su contenido.
    if archivos:

        archivo_id = archivos[0]["id"]

        drive.files().update(
            fileId=archivo_id,
            media_body=media
        ).execute()

        return {
            "accion": "actualizado",
            "archivo_id": archivo_id
        }

    # Si todavía no existe, lo creamos.
    metadata = {
        "name": nombre_archivo,
        "parents": [GOOGLE_DRIVE_FOLDER_ID]
    }

    creado = drive.files().create(
        body=metadata,
        media_body=media,
        fields="id"
    ).execute()

    return {
        "accion": "creado",
        "archivo_id": creado["id"]
    }


# ==========================================================
# SINCRONIZACIÓN SEGURA
# ==========================================================

def sincronizar_excel_seguro():
    correcto = True
    for nombre, generador in (
        (NOMBRE_ARCHIVO, generar_excel_servicios),
        (NOMBRE_TICKETS, generar_excel_tickets),
    ):
        try:
            resultado = sincronizar_excel_drive(nombre, generador)
            print(f"Excel Drive sincronizado: {nombre}: {resultado['accion']}")
        except Exception as error:
            print(f"ADVERTENCIA: No se pudo sincronizar {nombre}: {error}")
            correcto = False
    return correcto
