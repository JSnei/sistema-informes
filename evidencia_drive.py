import logging
import os
import re
from datetime import timedelta, timezone
from hashlib import sha256
from io import BytesIO

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from sqlalchemy.exc import IntegrityError

from database import database as db
from excel_drive import GOOGLE_DRIVE_FOLDER_ID, obtener_drive

MAX_FOTO = 10 * 1024 * 1024
MAX_VIDEO = 50 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024
FORMATOS = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp",
            "mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm"}
MESES = ("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
         "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")
logger = logging.getLogger(__name__)


def leer_fotos(archivos, firmado=False):
    minimo = 1 if firmado else 4
    if len(archivos) < minimo:
        raise ValueError("Adjunta al menos una foto del ticket firmado." if firmado else "Adjunta al menos cuatro fotos o videos de evidencia.")
    if len(archivos) > 999:
        raise ValueError("El envío admite hasta 999 fotos de evidencia.")
    fotos = []
    total = 0
    for archivo in archivos:
        contenido = archivo.file.read(MAX_VIDEO + 1)
        total += len(contenido)
        if total > MAX_TOTAL:
            raise ValueError("Los archivos juntos deben pesar como máximo 100 MB.")
        if contenido.startswith(b"\xff\xd8\xff"):
            formato = "jpg"
        elif contenido.startswith(b"\x89PNG\r\n\x1a\n"):
            formato = "png"
        elif contenido.startswith(b"RIFF") and contenido[8:12] == b"WEBP":
            formato = "webp"
        elif (len(contenido) >= 12 and contenido[4:8] == b"ftyp" and
              contenido[8:12] in (b"qt  ", b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ", b"MSNV", b"dash")):
            formato = "mov" if contenido[8:12] == b"qt  " else "mp4"
        elif contenido.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in contenido[:4096]:
            formato = "webm"
        else:
            raise ValueError("Usa imágenes JPG, PNG o WebP, o videos MP4, MOV o WebM.")
        video = formato in ("mp4", "mov", "webm")
        if firmado and video:
            raise ValueError("El ticket firmado debe adjuntarse como fotografía.")
        if len(contenido) > (MAX_VIDEO if video else MAX_FOTO):
            raise ValueError("Máximo 10 MB por foto y 50 MB por video.")
        fotos.append((formato, contenido))
    return fotos


def leer_adjuntos(evidencias, firmadas):
    if len(evidencias) + len(firmadas) > 999:
        raise ValueError("El envío admite hasta 999 archivos en total.")
    fotos = leer_fotos(evidencias)
    ticket = leer_fotos(firmadas, firmado=True)
    if sum(len(contenido) for _, contenido in fotos + ticket) > MAX_TOTAL:
        raise ValueError("Los archivos juntos deben pesar como máximo 100 MB.")
    return fotos, ticket


def listar_archivos(archivos, padre, solo_carpetas=False):
    padre = padre.replace("\\", "\\\\").replace("'", "\\'")
    consulta = f"'{padre}' in parents and trashed=false"
    if solo_carpetas:
        consulta += " and mimeType='application/vnd.google-apps.folder'"
    pagina = None
    resultado = []
    while True:
        respuesta = archivos.list(q=consulta, fields="nextPageToken,files(id,name)", pageSize=1000,
                                  pageToken=pagina, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        resultado.extend(respuesta.get("files", []))
        pagina = respuesta.get("nextPageToken")
        if not pagina:
            return resultado


def obtener_directorio(archivos, padre, nombre):
    clave = sha256(f"{padre}/{nombre.casefold()}".encode()).hexdigest()
    with db.SessionLocal() as sesion:
        registro = sesion.get(db.DirectorioDrive, clave)
        if registro is None:
            existente = next((c for c in listar_archivos(archivos, padre, True)
                              if c["name"].strip().casefold() == nombre.casefold()), None)
            carpeta_id = existente["id"] if existente else archivos.generateIds(count=1, space="drive").execute()["ids"][0]
            sesion.add(db.DirectorioDrive(clave=clave, carpeta_id=carpeta_id))
            try:
                sesion.commit()
            except IntegrityError:
                sesion.rollback()
            registro = sesion.get(db.DirectorioDrive, clave)
        carpeta_id = registro.carpeta_id
    crear_en_drive(archivos, {"id": carpeta_id, "name": nombre, "parents": [padre],
                              "mimeType": "application/vnd.google-apps.folder"})
    return carpeta_id


def crear_en_drive(archivos, datos, media=None):
    opciones = {"body": datos, "supportsAllDrives": True, "fields": "id"}
    if media is not None:
        opciones["media_body"] = media
    try:
        archivos.create(**opciones).execute()
    except HttpError as error:
        if error.resp.status != 409:
            raise
        existente = archivos.get(fileId=datos["id"], supportsAllDrives=True,
                                 fields="id,trashed,parents").execute()
        if existente.get("trashed") or datos["parents"][0] not in existente.get("parents", []):
            raise ValueError("El archivo existente no está en su ubicación esperada.")


def sincronizar_evidencia(servicio_id):
    """Conserva las fotos pendientes hasta confirmar su carga en Drive."""
    try:
        with db.SessionLocal() as sesion:
            carpeta = sesion.query(db.CarpetaEvidencia).filter_by(servicio_id=servicio_id).with_for_update().first()
            if carpeta is None:
                return True
            archivos = obtener_drive().files()
            servicio = sesion.get(db.Servicio, servicio_id)
            nombre = servicio.ticket
            if nombre == "000":
                solicitud_id = sesion.query(db.Ticket.id).filter_by(servicio_id=servicio_id).scalar()
                nombre = f"000 - Solicitud {solicitud_id or servicio.enlace_externo_id}"
            if not carpeta.carpeta_id:
                fotos = sesion.query(db.FotoEvidencia).filter_by(servicio_id=servicio_id).order_by(db.FotoEvidencia.posicion).all()
                padre = os.getenv("GOOGLE_DRIVE_EVIDENCE_FOLDER_ID") or GOOGLE_DRIVE_FOLDER_ID
                if not padre:
                    raise ValueError("Falta configurar la carpeta principal de evidencias en Drive.")
                fecha = servicio.fecha_registro
                if fecha.tzinfo is None:
                    fecha = fecha.replace(tzinfo=timezone.utc)
                fecha = fecha.astimezone(timezone(timedelta(hours=-5)))
                carpeta.carpeta_padre_id = obtener_directorio(archivos, padre, MESES[fecha.month - 1])
                carpeta.carpeta_id = obtener_directorio(archivos, carpeta.carpeta_padre_id, nombre)
                ids = archivos.generateIds(count=len(fotos), space="drive").execute()["ids"]
                existentes = listar_archivos(archivos, carpeta.carpeta_id)
                consecutivos = {"EVIDENCIA": 0, "FIRMADO": 0}
                for existente in existentes:
                    coincidencia = re.fullmatch(r"(F?)(\d+)(?:\.[^.]+)?", existente["name"], re.IGNORECASE)
                    if coincidencia:
                        tipo = "FIRMADO" if coincidencia[1] else "EVIDENCIA"
                        consecutivos[tipo] = max(consecutivos[tipo], int(coincidencia[2]))
                for foto, archivo_id in zip(fotos, ids, strict=True):
                    foto.archivo_id = archivo_id
                    consecutivos[foto.tipo] += 1
                    prefijo = "F" if foto.tipo == "FIRMADO" else ""
                    foto.nombre_drive = f"{prefijo}{consecutivos[foto.tipo]}.{foto.formato}"
                sesion.commit()

            carpeta = sesion.query(db.CarpetaEvidencia).filter_by(servicio_id=servicio_id).populate_existing().with_for_update().first()
            if carpeta is None:
                return True
            servicio = sesion.get(db.Servicio, servicio_id)
            nombre = servicio.ticket
            if nombre == "000":
                solicitud_id = sesion.query(db.Ticket.id).filter_by(servicio_id=servicio_id).scalar()
                nombre = f"000 - Solicitud {solicitud_id or servicio.enlace_externo_id}"
            if carpeta.sincronizada:
                archivos.update(fileId=carpeta.carpeta_id, body={"name": nombre}, supportsAllDrives=True).execute()
                return True

            padre = carpeta.carpeta_padre_id or os.getenv("GOOGLE_DRIVE_EVIDENCE_FOLDER_ID") or GOOGLE_DRIVE_FOLDER_ID
            crear_en_drive(archivos, {"id": carpeta.carpeta_id, "name": nombre, "parents": [padre],
                                      "mimeType": "application/vnd.google-apps.folder"})
            archivos.update(fileId=carpeta.carpeta_id, body={"name": nombre}, supportsAllDrives=True).execute()
            fotos = sesion.query(db.FotoEvidencia).filter_by(servicio_id=servicio_id).order_by(db.FotoEvidencia.posicion).all()
            for foto in fotos:
                media = MediaIoBaseUpload(BytesIO(foto.contenido), mimetype=FORMATOS[foto.formato])
                crear_en_drive(archivos, {"id": foto.archivo_id, "name": foto.nombre_drive or f"Evidencia {foto.posicion}.{foto.formato}",
                                          "parents": [carpeta.carpeta_id]}, media)
                foto.contenido = None
            carpeta.sincronizada = True
            sesion.commit()
            return True
    except Exception:
        logger.exception("No se pudo sincronizar la evidencia del servicio %s", servicio_id)
        return False
