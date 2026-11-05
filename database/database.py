import os
import secrets
import re
from dotenv import load_dotenv

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Numeric,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    inspect,
    text,
)

from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.exc import IntegrityError


# ==========================================================
# VARIABLES DE ENTORNO
# ==========================================================

load_dotenv()


# ==========================================================
# CONEXIÓN A POSTGRESQL
# ==========================================================

url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(
    url,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)

Base = declarative_base()


# ==========================================================
# MODELO: TÉCNICOS
# ==========================================================
#
# Credenciales:
#
# 101 - 199 = Técnicos CEDI
# 201 - 299 = Técnicos BS Electromecánica
#
# Los técnicos externos NO se registran aquí.
# Entrarán posteriormente mediante enlaces temporales.
#
# ==========================================================

class Tecnico(Base):
    __tablename__ = "tecnicos"

    id = Column(
        Integer,
        primary_key=True
    )

    credencial = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    nombre = Column(
        String(150),
        nullable=False
    )

    # El correo puede repetirse.
    # Varios técnicos pueden utilizar el mismo correo general.
    correo = Column(
        String(255),
        nullable=False
    )

    rol = Column(
        String(50),
        nullable=False
    )

    activo = Column(
        Boolean,
        nullable=False,
        default=True
    )

    fecha_creacion = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )


# ==========================================================
# MODELO: TIENDAS
# ==========================================================

class Tienda(Base):
    __tablename__ = "tiendas"

    id = Column(
        Integer,
        primary_key=True
    )

    # SAP / número de tienda.
    # Se almacena como texto porque es un identificador,
    # no un número para realizar operaciones matemáticas.
    sap = Column(
        String(30),
        unique=True,
        nullable=False,
        index=True
    )

    region = Column(
        String(20),
        nullable=True
    )

    tipo = Column(
        String(50),
        nullable=True
    )

    nombre = Column(
        String(200),
        nullable=False
    )

    ciudad = Column(
        String(150),
        nullable=True
    )

    departamento = Column(
        String(150),
        nullable=True
    )

    direccion = Column(
        String(300),
        nullable=True
    )

    activo = Column(
        Boolean,
        nullable=False,
        default=True
    )

    fecha_creacion = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

# ==========================================================
# MODELO: ENLACES PARA SERVICIOS EXTERNOS
# ==========================================================

class EnlaceExterno(Base):
    __tablename__ = "enlaces_externos"

    id = Column(
        Integer,
        primary_key=True
    )

    token = Column(
        String(150),
        unique=True,
        nullable=False,
        index=True
    )

    estado = Column(
        String(30),
        nullable=False,
        default="PENDIENTE"
    )

    # Define si el enlace corresponde
    # a un servicio REAL o de PRUEBA
    tipo_registro = Column(
        String(10),
        nullable=False,
        default="REAL"
    )

    fecha_creacion = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    fecha_utilizado = Column(
        DateTime(timezone=True),
        nullable=True
    )


class Ticket(Base):
    __tablename__ = "tickets"
    precio = Column(Numeric(12, 2), nullable=True)

    id = Column(Integer, primary_key=True)
    # NULL representa 000: varias solicitudes pueden esperar número.
    numero = Column(String(100), unique=True, nullable=True, index=True)
    tienda_id = Column(Integer, ForeignKey("tiendas.id"), nullable=False)
    prioridad = Column(String(20), nullable=False, default="MEDIA")
    fecha_reporte = Column(DateTime, nullable=False)
    contacto = Column(String(150), nullable=True)
    telefonos = Column(String(150), nullable=True)
    registrado_por = Column(String(150), nullable=True)
    coordinador = Column(String(150), nullable=True)
    codigo = Column(String(100), nullable=True)
    equipo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), unique=True, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TicketEnlace(Base):
    """Vincula solicitudes y enlaces sin modificar las tablas existentes."""
    __tablename__ = "tickets_enlaces"
    ticket_id = Column(Integer, ForeignKey("tickets.id"), primary_key=True)
    enlace_id = Column(Integer, ForeignKey("enlaces_externos.id"), nullable=False, unique=True)


class Servicio(Base):
    __tablename__ = "servicios"

    id = Column(Integer, primary_key=True)

    # Tienda donde se realizó el servicio
    tienda_id = Column(
        Integer,
        ForeignKey("tiendas.id"),
        nullable=False,
        index=True
    )

    # Enlace externo con el que se creó
    enlace_externo_id = Column(
        Integer,
        ForeignKey("enlaces_externos.id"),
        nullable=False,
        unique=True,
        index=True
    )

    # Información general
    ticket = Column(
        String(100),
        nullable=False,
        index=True
    )

    tipo_servicio = Column(
        String(50),
        nullable=False
    )

    # Técnico externo
    cedula_tecnico = Column(
        String(30),
        nullable=False
    )

    nombre_tecnico = Column(
        String(150),
        nullable=False
    )

    telefono_tecnico = Column(String(30), nullable=True)

    # Encargado de la tienda
    sap_encargado = Column(
        String(50),
        nullable=False
    )

    nombre_encargado = Column(
        String(150),
        nullable=False
    )

    # Información técnica
    descripcion_falla = Column(
        Text,
        nullable=False
    )

    trabajo_realizado = Column(
        Text,
        nullable=False
    )

    observaciones = Column(
        Text,
        nullable=True
    )

    # Repuestos
    suministro_repuestos = Column(
        Boolean,
        nullable=False,
        default=False
    )

    repuestos_suministrados = Column(
        Text,
        nullable=True
    )

    # Tipo de registro
    # REAL = servicio verdadero
    # PRUEBA = registro utilizado para comprobar el sistema
    tipo_registro = Column(
        String(10),
        nullable=False,
        default="REAL"
    )

    # Estado del servicio
    estado = Column(
        String(30),
        nullable=False,
        default="REGISTRADO"
    )

    # Fecha automática
    fecha_registro = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )


# ==========================================================
# CREAR TABLAS
# ==========================================================

def crear_base_datos():
    Base.metadata.create_all(bind=engine)
    # create_all no agrega columnas a instalaciones existentes.
    with engine.begin() as conexion:
        columnas_ticket = {c["name"] for c in inspect(conexion).get_columns("tickets")}
        if "precio" not in columnas_ticket:
            condicional = "IF NOT EXISTS " if conexion.dialect.name == "postgresql" else ""
            conexion.execute(text(f"ALTER TABLE tickets ADD COLUMN {condicional}precio NUMERIC(12, 2)"))
        columnas = {c["name"] for c in inspect(conexion).get_columns("servicios")}
        if "telefono_tecnico" not in columnas:
            condicional = "IF NOT EXISTS " if conexion.dialect.name == "postgresql" else ""
            conexion.execute(text(f"ALTER TABLE servicios ADD COLUMN {condicional}telefono_tecnico VARCHAR(30)"))


# ==========================================================
# DETERMINAR TIPO DE TÉCNICO POR CREDENCIAL
# ==========================================================

def obtener_grupo_por_credencial(credencial):

    try:
        numero = int(credencial)
    except (ValueError, TypeError):
        return None

    if 101 <= numero <= 199:
        return "CEDI"

    if 201 <= numero <= 299:
        return "EMPRESA"

    if 301 <= numero <= 399:
        return "RESERVADO"

    if 401 <= numero <= 499:
        return "SERVICIOS_EXTERNOS"

    return None


# ==========================================================
# OBTENER TODOS LOS TÉCNICOS
# ==========================================================

def obtener_tecnicos():

    with SessionLocal() as db:

        tecnicos = (
            db.query(Tecnico)
            .order_by(Tecnico.nombre.asc())
            .all()
        )

        return tecnicos


# ==========================================================
# OBTENER TÉCNICO POR ID
# ==========================================================

def obtener_tecnico(id_tecnico):

    with SessionLocal() as db:

        tecnico = (
            db.query(Tecnico)
            .filter(Tecnico.id == id_tecnico)
            .first()
        )

        return tecnico


# ==========================================================
# OBTENER TÉCNICO POR CREDENCIAL
# ==========================================================

def obtener_tecnico_por_credencial(credencial):

    with SessionLocal() as db:

        tecnico = (
            db.query(Tecnico)
            .filter(Tecnico.credencial == str(credencial))
            .first()
        )

        return tecnico


# ==========================================================
# AGREGAR TÉCNICO
# ==========================================================

def agregar_tecnico(
    credencial,
    nombre,
    correo,
    rol
):

    grupo = obtener_grupo_por_credencial(credencial)

    if grupo is None:
        raise ValueError(
            "La credencial debe pertenecer a uno de los rangos permitidos: "
            "101-199 CEDI, 201-299 BS Electromecánica, "
            "301-399 reservado o 401-499 Servicios Externos."
        )

    rol = str(rol).strip()

    # ----------------------------------------------------------
    # VALIDAR GRUPO 300
    # ----------------------------------------------------------
    # Este rango queda reservado para uso futuro.
    if grupo == "RESERVADO":
        raise ValueError(
            "Las credenciales 301-399 están reservadas "
            "y actualmente no pueden utilizarse."
        )

    # ----------------------------------------------------------
    # VALIDAR OPERADORES DE SERVICIOS EXTERNOS
    # ----------------------------------------------------------
    # Solo las credenciales 401-499 pueden tener este rol.
    if rol == "operador_servicios_externos":
        if grupo != "SERVICIOS_EXTERNOS":
            raise ValueError(
                "El perfil Operador de servicios externos "
                "solo puede utilizar credenciales entre 401 y 499."
            )

    # Una credencial 401-499 obligatoriamente debe tener
    # el rol de operador de servicios externos.
    if grupo == "SERVICIOS_EXTERNOS":
        if rol != "operador_servicios_externos":
            raise ValueError(
                "Las credenciales 401-499 deben utilizar el perfil "
                "Operador de servicios externos."
            )

    with SessionLocal() as db:

        existente = (
            db.query(Tecnico)
            .filter(
                Tecnico.credencial == str(credencial)
            )
            .first()
        )

        if existente:
            raise ValueError(
                "Ya existe un técnico con esa credencial."
            )

        tecnico = Tecnico(
            credencial=str(credencial),
            nombre=nombre.strip(),
            correo=correo.strip(),
            rol=rol,
            activo=True
        )

        db.add(tecnico)
        db.commit()
        db.refresh(tecnico)

        return tecnico


# ==========================================================
# EDITAR TÉCNICO
# ==========================================================

def editar_tecnico(
    id_tecnico,
    credencial,
    nombre,
    correo,
    rol
):

    grupo = obtener_grupo_por_credencial(credencial)

    if grupo is None:
        raise ValueError(
            "La credencial debe pertenecer a uno de los rangos permitidos: "
            "101-199 CEDI, 201-299 BS Electromecánica, "
            "301-399 reservado o 401-499 Servicios Externos."
        )

    rol = str(rol).strip()

    # ----------------------------------------------------------
    # VALIDAR GRUPO 300
    # ----------------------------------------------------------
    # Este rango queda reservado para uso futuro.
    if grupo == "RESERVADO":
        raise ValueError(
            "Las credenciales 301-399 están reservadas "
            "y actualmente no pueden utilizarse."
        )

    # ----------------------------------------------------------
    # VALIDIDAR OPERADOR DE SERVICIOS EXTERNOS
    # ----------------------------------------------------------
    # Solo las credenciales 401-499 pueden tener este rol.
    if rol == "operador_servicios_externos":
        if grupo != "SERVICIOS_EXTERNOS":
            raise ValueError(
                "El perfil Operador de servicios externos "
                "solo puede utilizar credenciales entre 401 y 499."
            )

    # Toda credencial 401-499 debe conservar este rol.
    if grupo == "SERVICIOS_EXTERNOS":
        if rol != "operador_servicios_externos":
            raise ValueError(
                "Las credenciales 401-499 deben utilizar el perfil "
                "Operador de servicios externos."
            )

    with SessionLocal() as db:

        tecnico = (
            db.query(Tecnico)
            .filter(
                Tecnico.id == id_tecnico
            )
            .first()
        )

        if tecnico is None:
            return None

        credencial_existente = (
            db.query(Tecnico)
            .filter(
                Tecnico.credencial == str(credencial),
                Tecnico.id != id_tecnico
            )
            .first()
        )

        if credencial_existente:
            raise ValueError(
                "Ya existe otro técnico con esa credencial."
            )

        tecnico.credencial = str(credencial)
        tecnico.nombre = nombre.strip()
        tecnico.correo = correo.strip()
        tecnico.rol = rol

        db.commit()

        return True


# ==========================================================
# ACTIVAR / DESACTIVAR TÉCNICO
# ==========================================================

def cambiar_estado_tecnico(id_tecnico):

    with SessionLocal() as db:

        tecnico = (
            db.query(Tecnico)
            .filter(
                Tecnico.id == id_tecnico
            )
            .first()
        )

        if tecnico is None:
            return None

        tecnico.activo = not tecnico.activo

        db.commit()

        return True


# ==========================================================
# ELIMINAR TÉCNICO
# ==========================================================

def eliminar_tecnico(id_tecnico):

    with SessionLocal() as db:

        tecnico = (
            db.query(Tecnico)
            .filter(
                Tecnico.id == id_tecnico
            )
            .first()
        )

        if tecnico is None:
            return None

        db.delete(tecnico)
        db.commit()

        return True


# ==========================================================
# OBTENER TODAS LAS TIENDAS
# ==========================================================

def obtener_tiendas():

    with SessionLocal() as db:

        tiendas = (
            db.query(Tienda)
            .order_by(Tienda.nombre.asc())
            .all()
        )

        return tiendas


# ==========================================================
# OBTENER TIENDA POR ID
# ==========================================================

def obtener_tienda(id_tienda):

    with SessionLocal() as db:

        tienda = (
            db.query(Tienda)
            .filter(Tienda.id == id_tienda)
            .first()
        )

        return tienda


# ==========================================================
# OBTENER TIENDA POR SAP
# ==========================================================

def obtener_tienda_por_sap(sap):

    sap = str(sap).strip()

    with SessionLocal() as db:

        tienda = (
            db.query(Tienda)
            .filter(Tienda.sap == sap)
            .first()
        )

        return tienda


def obtener_tienda_por_id(id_tienda):

    with SessionLocal() as db:

        tienda = (
            db.query(Tienda)
            .filter(Tienda.id == id_tienda)
            .first()
        )

        return tienda


# ==========================================================
# AGREGAR TIENDA
# ==========================================================

def agregar_tienda(
    sap,
    region,
    tipo,
    nombre,
    ciudad,
    departamento,
    direccion
):

    sap = str(sap).strip()

    if not sap:
        raise ValueError(
            "El número SAP de la tienda es obligatorio."
        )

    with SessionLocal() as db:

        existente = (
            db.query(Tienda)
            .filter(Tienda.sap == sap)
            .first()
        )

        if existente:
            raise ValueError(
                "Ya existe una tienda con ese número SAP."
            )

        tienda = Tienda(
            sap=sap,
            region=str(region).strip() if region is not None else None,
            tipo=str(tipo).strip() if tipo is not None else None,
            nombre=str(nombre).strip(),
            ciudad=str(ciudad).strip() if ciudad is not None else None,
            departamento=(
                str(departamento).strip()
                if departamento is not None
                else None
            ),
            direccion=(
                str(direccion).strip()
                if direccion is not None
                else None
            ),
            activo=True
        )

        db.add(tienda)
        db.commit()
        db.refresh(tienda)

        return tienda


# ==========================================================
# EDITAR TIENDA
# ==========================================================

def editar_tienda(
    id_tienda,
    sap,
    region,
    tipo,
    nombre,
    ciudad,
    departamento,
    direccion
):

    sap = str(sap).strip()

    with SessionLocal() as db:

        tienda = (
            db.query(Tienda)
            .filter(Tienda.id == id_tienda)
            .first()
        )

        if tienda is None:
            return None

        sap_existente = (
            db.query(Tienda)
            .filter(
                Tienda.sap == sap,
                Tienda.id != id_tienda
            )
            .first()
        )

        if sap_existente:
            raise ValueError(
                "Ya existe otra tienda con ese número SAP."
            )

        tienda.sap = sap
        tienda.region = (
            str(region).strip()
            if region is not None
            else None
        )
        tienda.tipo = (
            str(tipo).strip()
            if tipo is not None
            else None
        )
        tienda.nombre = str(nombre).strip()
        tienda.ciudad = (
            str(ciudad).strip()
            if ciudad is not None
            else None
        )
        tienda.departamento = (
            str(departamento).strip()
            if departamento is not None
            else None
        )
        tienda.direccion = (
            str(direccion).strip()
            if direccion is not None
            else None
        )

        db.commit()

        return True


# ==========================================================
# ACTIVAR / DESACTIVAR TIENDA
# ==========================================================

def cambiar_estado_tienda(id_tienda):

    with SessionLocal() as db:

        tienda = (
            db.query(Tienda)
            .filter(Tienda.id == id_tienda)
            .first()
        )

        if tienda is None:
            return None

        tienda.activo = not tienda.activo

        db.commit()

        return True


# ==========================================================
# CREAR ENLACE EXTERNO
# ==========================================================

def crear_enlace_externo(token, tipo_registro="REAL"):

    tipo_registro = str(tipo_registro).strip().upper()

    # Solo permitimos estos dos valores
    if tipo_registro not in ["REAL", "PRUEBA"]:
        raise ValueError(
            "El tipo de registro debe ser REAL o PRUEBA."
        )

    with SessionLocal() as db:

        enlace = EnlaceExterno(
            token=token,
            estado="PENDIENTE",
            tipo_registro=tipo_registro
        )

        db.add(enlace)
        db.commit()
        db.refresh(enlace)

        return enlace


# ==========================================================
# OBTENER ENLACE EXTERNO POR TOKEN
# ==========================================================

def obtener_enlace_externo(token):

    with SessionLocal() as db:

        enlace = (
            db.query(EnlaceExterno)
            .filter(
                EnlaceExterno.token == token
            )
            .first()
        )

        return enlace


# ==========================================================
# OBTENER TODOS LOS ENLACES EXTERNOS
# ==========================================================

def obtener_enlaces_externos():

    with SessionLocal() as db:

        enlaces = (
            db.query(EnlaceExterno)
            .order_by(
                EnlaceExterno.fecha_creacion.desc()
            )
            .all()
        )

        return enlaces


# ==========================================================
# CANCELAR ENLACE EXTERNO
# ==========================================================

def cancelar_enlace_externo(id_enlace):

    with SessionLocal() as db:

        enlace = (
            db.query(EnlaceExterno)
            .filter(
                EnlaceExterno.id == id_enlace
            )
            .first()
        )

        if enlace is None:
            return None

        enlace.estado = "CANCELADO"

        db.commit()

        return True


def crear_servicio_externo(
        
    token,
    sap_tienda,
    ticket,
    tipo_servicio,
    cedula_tecnico,
    nombre_tecnico,
    sap_encargado,
    nombre_encargado,
    descripcion_falla,
    trabajo_realizado,
    observaciones,
    suministro_repuestos,
    repuestos_suministrados,
    tipo_registro="REAL",
    ticket_solicitud_id=None,
    telefono_tecnico=""
):
    telefono_tecnico = telefono_tecnico.strip()
    digitos = re.sub(r"[^0-9]", "", telefono_tecnico)
    if (len(telefono_tecnico) > 30 or not 7 <= len(digitos) <= 15
            or not re.fullmatch(r"\+?[0-9 ()-]+", telefono_tecnico)):
        raise ValueError("Ingresa un teléfono válido del técnico, con entre 7 y 15 dígitos.")
    with SessionLocal() as db:


        # ------------------------------------------
        # 1. VERIFICAR EL ENLACE
        # ------------------------------------------

        enlace = (
            db.query(EnlaceExterno)
            .filter(EnlaceExterno.token == token)
            .with_for_update()
            .first()
        )

        if enlace is None:
            raise ValueError("El enlace no existe.")

        if enlace.estado != "PENDIENTE":
            raise ValueError("Este enlace ya no está disponible.")


        # ------------------------------------------
        # 2. VERIFICAR LA TIENDA
        # ------------------------------------------

        sap_tienda = str(sap_tienda).strip()

        tienda = (
            db.query(Tienda)
            .filter(Tienda.sap == sap_tienda)
            .first()
        )

        if tienda is None:
            raise ValueError(
                "La tienda no está registrada en el sistema."
            )

        if not tienda.activo:
            raise ValueError(
                "La tienda se encuentra deshabilitada."
            )

        # El bloqueo serializa registros simultáneos del mismo ticket.
        vinculo = db.query(TicketEnlace).filter(TicketEnlace.enlace_id == enlace.id).first()
        if vinculo:
            if ticket_solicitud_id and ticket_solicitud_id != vinculo.ticket_id:
                raise ValueError("Este enlace solo permite registrar la solicitud para la que fue creado.")
            ticket_solicitud_id = vinculo.ticket_id
        ticket_registrado = buscar_ticket(db, ticket, tienda.id, ticket_solicitud_id, bloquear=True)
        validar_ticket_servicio(db, ticket_registrado, tienda.id)
        ticket = ticket_registrado.numero or "000"
        # El tipo de registro lo determina siempre el enlace.
        tipo_registro = enlace.tipo_registro


        # ------------------------------------------
        # 3. VALIDAR REPUESTOS
        # ------------------------------------------

        suministro_repuestos = (
            str(suministro_repuestos)
            .strip()
            .upper()
        )

        if suministro_repuestos not in ["SI", "NO"]:
            raise ValueError(
                "Debes indicar si se suministraron repuestos."
            )

        if suministro_repuestos == "SI":

            repuestos_suministrados = (
                str(repuestos_suministrados).strip()
            )

            if not repuestos_suministrados:
                raise ValueError(
                    "Debes indicar los repuestos suministrados."
                )

            suministro_booleano = True

        else:

            suministro_booleano = False
            repuestos_suministrados = None


        # ------------------------------------------
        # 4. CREAR EL SERVICIO
        # ------------------------------------------

        servicio = Servicio(
            tienda_id=tienda.id,
            enlace_externo_id=enlace.id,

            ticket=str(ticket).strip(),
            tipo_servicio=str(tipo_servicio).strip(),

            cedula_tecnico=str(cedula_tecnico).strip(),
            nombre_tecnico=str(nombre_tecnico).strip(),
            telefono_tecnico=telefono_tecnico.strip() or None,

            sap_encargado=str(sap_encargado).strip(),
            nombre_encargado=str(nombre_encargado).strip(),

            descripcion_falla=str(descripcion_falla).strip(),
            trabajo_realizado=str(trabajo_realizado).strip(),

            observaciones=(
                str(observaciones).strip()
                if observaciones
                else None
            ),

            suministro_repuestos=suministro_booleano,

            repuestos_suministrados=repuestos_suministrados,

            tipo_registro=str(tipo_registro).strip().upper(),

            estado="REGISTRADO"
        )

        db.add(servicio)
        db.flush()
        if tipo_registro == "REAL":
            ticket_registrado.servicio_id = servicio.id


        # ------------------------------------------
        # 5. MARCAR ENLACE COMO UTILIZADO
        # ------------------------------------------

        enlace.estado = "UTILIZADO"
        enlace.fecha_utilizado = func.now()


        # ------------------------------------------
        # 6. GUARDAR TODO
        # ------------------------------------------

        try:

            db.commit()
            db.refresh(servicio)

            return servicio.id

        except Exception:


            db.rollback()
            raise


def eliminar_servicio_prueba(servicio_id):

    with SessionLocal() as db:

        servicio = (
            db.query(Servicio)
            .filter(Servicio.id == servicio_id)
            .first()
        )

        if servicio is None:
            raise ValueError("El servicio no existe.")

        # SEGURIDAD:
        # Los servicios REALES nunca se eliminan físicamente.
        if servicio.tipo_registro != "PRUEBA":
            raise ValueError(
                "No está permitido eliminar un servicio REAL."
            )

        enlace_id = servicio.enlace_externo_id

        # Eliminamos primero el servicio
        db.delete(servicio)
        db.flush()

        # Eliminamos también el enlace de PRUEBA asociado
        enlace = (
            db.query(EnlaceExterno)
            .filter(EnlaceExterno.id == enlace_id)
            .first()
        )

        if enlace is not None:
            db.delete(enlace)

        db.commit()

        return True


def anular_servicio_real(servicio_id):

    with SessionLocal() as db:

        servicio = (
            db.query(Servicio)
            .filter(Servicio.id == servicio_id)
            .first()
        )

        if servicio is None:
            raise ValueError("El servicio no existe.")

        # Solo se pueden anular servicios REALES
        if servicio.tipo_registro != "REAL":
            raise ValueError(
                "Esta función solo permite anular servicios REALES."
            )

        # Evitamos anularlo dos veces
        if servicio.estado == "ANULADO":
            raise ValueError(
                "Este servicio ya se encuentra anulado."
            )

        servicio.estado = "ANULADO"

        db.commit()

        return True


def obtener_servicios():

    with SessionLocal() as db:

        # Partimos de TODOS los enlaces generados.
        # Así también aparecen los que aún no han sido diligenciados.
        resultados = (
            db.query(
                EnlaceExterno,
                Servicio
            )
            .outerjoin(
                Servicio,
                Servicio.enlace_externo_id == EnlaceExterno.id
            )
            .order_by(
                EnlaceExterno.fecha_creacion.desc()
            )
            .all()
        )

        servicios_admin = []

        for enlace, servicio in resultados:

            # Determinamos el estado que verá el administrador
            if enlace.estado == "CANCELADO":
                estado_admin = "CANCELADO"

            elif servicio is not None and servicio.estado == "ANULADO":
                estado_admin = "ANULADO"

            elif servicio is not None:
                estado_admin = "REALIZADO"

            else:
                estado_admin = "PENDIENTE"

            servicios_admin.append({
                "enlace_id": enlace.id,
                "token": enlace.token,
                "tipo_registro": enlace.tipo_registro,
                "estado": estado_admin,
                "fecha_generado": enlace.fecha_creacion,

                # Si todavía no se ha realizado,
                # estos datos quedan vacíos.
                "servicio_id": servicio.id if servicio else None,
                "ticket": servicio.ticket if servicio else None,
                "tipo_servicio": servicio.tipo_servicio if servicio else None,
                "cedula_tecnico": servicio.cedula_tecnico if servicio else None,
                "nombre_tecnico": servicio.nombre_tecnico if servicio else None,
                "telefono_tecnico": servicio.telefono_tecnico if servicio else None,
                "fecha_realizado": servicio.fecha_registro if servicio else None
            })

        return servicios_admin


def obtener_servicios_para_excel():

    with SessionLocal() as db:

        resultados = (
            db.query(
                Servicio,
                Tienda
            )
            .join(
                Tienda,
                Servicio.tienda_id == Tienda.id
            )
            .filter(
                Servicio.tipo_registro == "REAL"
            )
            .order_by(
                Servicio.id.asc()
            )
            .all()
        )

        datos = []

        for servicio, tienda in resultados:

            datos.append({
                "servicio_id": servicio.id,
                "solicitud_id": servicio.enlace_externo_id,
                "fecha": servicio.fecha_registro,

                "ticket": servicio.ticket,

                "sap_tienda": tienda.sap,
                "nombre_tienda": tienda.nombre,
                "ciudad": tienda.ciudad,
                "departamento": tienda.departamento,
                "direccion": tienda.direccion,
                "region": tienda.region,
                "tipo_tienda": tienda.tipo,

                "tipo_servicio": servicio.tipo_servicio,

                "cedula_tecnico": servicio.cedula_tecnico,
                "nombre_tecnico": servicio.nombre_tecnico,
                "telefono_tecnico": servicio.telefono_tecnico,

                "sap_encargado": servicio.sap_encargado,
                "nombre_encargado": servicio.nombre_encargado,

                "descripcion_falla": servicio.descripcion_falla,
                "trabajo_realizado": servicio.trabajo_realizado,
                "observaciones": servicio.observaciones,

                "suministro_repuestos": (
                    "SI" if servicio.suministro_repuestos else "NO"
                ),

                "repuestos_suministrados":
                    servicio.repuestos_suministrados,

                "estado": servicio.estado
            })

        return datos


def obtener_tiendas():
    with SessionLocal() as db:
        return (
            db.query(Tienda)
            .order_by(Tienda.sap.asc())
            .all()
        )


def agregar_tienda(
    sap,
    region,
    tipo,
    nombre,
    ciudad,
    departamento,
    direccion
):
    sap = str(sap).strip()

    with SessionLocal() as db:

        tienda_existente = (
            db.query(Tienda)
            .filter(Tienda.sap == sap)
            .first()
        )

        if tienda_existente:
            return False

        nueva_tienda = Tienda(
            sap=sap,
            region=region.strip() if region else None,
            tipo=tipo.strip() if tipo else None,
            nombre=nombre.strip(),
            ciudad=ciudad.strip() if ciudad else None,
            departamento=departamento.strip() if departamento else None,
            direccion=direccion.strip() if direccion else None,
            activo=True
        )

        db.add(nueva_tienda)
        db.commit()

        return True


def editar_tienda(
    id_tienda,
    region,
    tipo,
    nombre,
    ciudad,
    departamento,
    direccion
):
    with SessionLocal() as db:

        tienda = (
            db.query(Tienda)
            .filter(Tienda.id == id_tienda)
            .first()
        )

        if tienda is None:
            return False

        # El SAP NO se modifica.
        # Es el identificador único de la tienda.

        tienda.region = (
            region.strip()
            if region
            else None
        )

        tienda.tipo = (
            tipo.strip()
            if tipo
            else None
        )

        tienda.nombre = nombre.strip()

        tienda.ciudad = (
            ciudad.strip()
            if ciudad
            else None
        )

        tienda.departamento = (
            departamento.strip()
            if departamento
            else None
        )

        tienda.direccion = (
            direccion.strip()
            if direccion
            else None
        )

        db.commit()

        return True


def cambiar_estado_tienda(id_tienda, activo):
    with SessionLocal() as db:

        tienda = (
            db.query(Tienda)
            .filter(Tienda.id == id_tienda)
            .first()
        )

        if tienda is None:
            return False

        tienda.activo = activo

        db.commit()

        return True


def normalizar_ticket(numero):
    return str(numero).strip().upper()


def servicio_real_ticket(db, numero):
    return db.query(Servicio).filter(
        func.upper(func.trim(Servicio.ticket)) == numero,
        Servicio.tipo_registro == "REAL",
        Servicio.estado != "ANULADO"
    ).order_by(Servicio.fecha_registro.desc()).first()


def validar_ticket_servicio(db, ticket, tienda_id):
    if ticket is None:
        raise ValueError("El ticket no está registrado. Solicita su registro a la oficina.")
    if ticket.tienda_id != tienda_id:
        raise ValueError("El ticket pertenece a otra tienda.")
    servicio = db.get(Servicio, ticket.servicio_id) if ticket.servicio_id else None
    if (servicio and servicio.estado != "ANULADO") or (
        ticket.numero and servicio_real_ticket(db, ticket.numero)
    ):
        raise ValueError("Este ticket ya tiene un servicio realizado.")


def buscar_ticket(db, numero, tienda_id, solicitud_id=None, bloquear=False):
    numero = normalizar_ticket(numero)
    consulta = db.query(Ticket)
    if solicitud_id:
        consulta = consulta.filter(Ticket.id == solicitud_id)
    else:
        if numero == "000":
            raise ValueError("Selecciona la solicitud sin número de ticket que corresponde al servicio.")
        consulta = consulta.filter(Ticket.numero == numero)
    if bloquear:
        consulta = consulta.with_for_update()
    ticket = consulta.first()
    if ticket and (ticket.numero or "000") != numero:
        raise ValueError("El número no corresponde a la solicitud seleccionada. Verifica el ticket nuevamente.")
    return ticket


def validar_datos_ticket(numero, sap_tienda, prioridad, fecha_reporte, equipo,
                     descripcion, contacto="", telefonos="", registrado_por="",
                     coordinador="", codigo=""):
    numero = normalizar_ticket(numero)
    if not numero or len(numero) > 100:
        raise ValueError("El número de ticket es obligatorio y admite hasta 100 caracteres.")
    prioridad = prioridad.strip().upper()
    if prioridad not in ("BAJA", "MEDIA", "ALTA", "URGENTE"):
        raise ValueError("La prioridad seleccionada no es válida.")
    equipo = equipo.strip()
    if not equipo or len(equipo) > 200 or not descripcion.strip():
        raise ValueError("Completa el equipo (máximo 200 caracteres) y la descripción.")
    for valor, limite in ((contacto, 150), (telefonos, 150), (registrado_por, 150),
                          (coordinador, 150), (codigo, 100)):
        if len(valor.strip()) > limite:
            raise ValueError(f"Uno de los campos supera el máximo de {limite} caracteres.")
    from datetime import datetime
    try:
        fecha = datetime.fromisoformat(fecha_reporte)
        if fecha.tzinfo is not None:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Ingresa una fecha y hora de reporte válida.")
    return dict(numero=None if numero == "000" else numero, prioridad=prioridad,
                fecha_reporte=fecha, equipo=equipo, descripcion=descripcion.strip(),
                contacto=contacto.strip(), telefonos=telefonos.strip(),
                registrado_por=registrado_por.strip(), coordinador=coordinador.strip(), codigo=codigo.strip())


def registrar_ticket(**datos):
    campos = validar_datos_ticket(**datos)
    with SessionLocal() as db:
        sap_tienda = datos["sap_tienda"]
        tienda = db.query(Tienda).filter(Tienda.sap == str(sap_tienda).strip()).first()
        if tienda is None or not tienda.activo:
            raise ValueError("Selecciona una tienda registrada y activa.")
        ticket = Ticket(tienda_id=tienda.id, **campos)
        db.add(ticket)
        try:
            db.flush()
            enlace = EnlaceExterno(token=secrets.token_urlsafe(32), tipo_registro="REAL", estado="PENDIENTE")
            db.add(enlace)
            db.flush()
            db.add(TicketEnlace(ticket_id=ticket.id, enlace_id=enlace.id))
            db.commit()
            return ticket.id
        except IntegrityError:
            db.rollback()
            raise ValueError("Ya existe un ticket con ese número.")


def consultar_ticket_servicio(numero, sap_tienda):
    with SessionLocal() as db:
        tienda = db.query(Tienda).filter(Tienda.sap == str(sap_tienda).strip()).first()
        if tienda is None or not tienda.activo:
            raise ValueError("La tienda no está disponible.")
        numero = normalizar_ticket(numero)
        if numero == "000":
            candidatos = db.query(Ticket).filter(
                Ticket.numero.is_(None), Ticket.tienda_id == tienda.id
            ).order_by(Ticket.id.desc()).all()
            disponibles = []
            for ticket in candidatos:
                try:
                    validar_ticket_servicio(db, ticket, tienda.id)
                except ValueError:
                    continue
                disponibles.append({"id": ticket.id, "numero": "000",
                    "equipo": ticket.equipo, "descripcion": ticket.descripcion,
                    "fecha_reporte": ticket.fecha_reporte.isoformat(),
                    "prioridad": ticket.prioridad})
            if not disponibles:
                raise ValueError("No hay solicitudes sin número pendientes para esta tienda. Solicita su registro a la oficina.")
            return disponibles
        ticket = buscar_ticket(db, numero, tienda.id)
        validar_ticket_servicio(db, ticket, tienda.id)
        return [{"id": ticket.id, "numero": ticket.numero, "equipo": ticket.equipo,
                 "descripcion": ticket.descripcion, "prioridad": ticket.prioridad,
                 "fecha_reporte": ticket.fecha_reporte.isoformat()}]


def obtener_tickets():
    with SessionLocal() as db:
        # Una sola consulta de servicios para construir el resumen sin N+1.
        realizados = db.query(Servicio).filter(
            Servicio.tipo_registro == "REAL", Servicio.estado != "ANULADO"
        ).order_by(Servicio.fecha_registro.asc()).all()
        por_numero = {normalizar_ticket(s.ticket): s for s in realizados}
        enlaces = {v.ticket_id: e for v, e in db.query(TicketEnlace, EnlaceExterno).join(
            EnlaceExterno, TicketEnlace.enlace_id == EnlaceExterno.id).all()}
        resultado = []
        for ticket, tienda in db.query(Ticket, Tienda).join(
            Tienda, Ticket.tienda_id == Tienda.id
        ).order_by(Ticket.fecha_creacion.desc(), Ticket.id.desc()).all():
            servicio = db.get(Servicio, ticket.servicio_id) if ticket.servicio_id else por_numero.get(ticket.numero)
            if servicio and servicio.estado == "ANULADO":
                servicio = None
            resultado.append({
                "precio": ticket.precio, "id": ticket.id, "numero": ticket.numero or "000", "equipo": ticket.equipo,
                "prioridad": ticket.prioridad, "fecha_reporte": ticket.fecha_reporte,
                "contacto": ticket.contacto, "telefonos": ticket.telefonos,
                "registrado_por": ticket.registrado_por, "coordinador": ticket.coordinador,
                "codigo": ticket.codigo, "direccion": tienda.direccion, "ciudad": tienda.ciudad,
                "descripcion": ticket.descripcion, "sap": tienda.sap,
                "tienda": tienda.nombre, "fecha_creacion": ticket.fecha_creacion,
                "estado": "REALIZADO" if servicio else "PENDIENTE",
                "estado_ticket": "ASIGNADO" if ticket.numero else "FALTANTE POR NÚMERO DE TICKET",
                "fecha_realizado": servicio.fecha_registro if servicio else None,
                "tecnico": servicio.nombre_tecnico if servicio else None,
                "telefono_tecnico": servicio.telefono_tecnico if servicio else None,
                "servicio_id": servicio.id if servicio else None,
                "token": enlaces[ticket.id].token if ticket.id in enlaces else None,
                "estado_enlace": enlaces[ticket.id].estado if ticket.id in enlaces else None
            })
        return resultado


def asignar_numero_ticket(solicitud_id, numero):
    numero = normalizar_ticket(numero)
    if not numero or numero == "000" or len(numero) > 100:
        raise ValueError("Ingresa el número real del ticket (máximo 100 caracteres).")
    with SessionLocal() as db:
        ticket = db.query(Ticket).filter(Ticket.id == solicitud_id).with_for_update().first()
        if ticket is None or ticket.numero is not None:
            raise ValueError("La solicitud no existe o ya tiene número de ticket.")
        if db.query(Ticket).filter(Ticket.numero == numero).first() or servicio_real_ticket(db, numero):
            raise ValueError("Ese número ya está registrado en otro ticket o servicio.")
        ticket.numero = numero
        if ticket.servicio_id:
            db.get(Servicio, ticket.servicio_id).ticket = numero
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError("Ese número de ticket ya está registrado.")


def obtener_solicitud_enlace(token):
    with SessionLocal() as db:
        fila = db.query(Ticket, Tienda).join(Tienda, Ticket.tienda_id == Tienda.id).join(
            TicketEnlace, TicketEnlace.ticket_id == Ticket.id
        ).join(EnlaceExterno, EnlaceExterno.id == TicketEnlace.enlace_id).filter(
            EnlaceExterno.token == token).first()
        if fila is None:
            return None
        ticket, tienda = fila
        return {"id": ticket.id, "numero": ticket.numero or "000", "sap": tienda.sap,
                "tienda": tienda, "equipo": ticket.equipo, "descripcion": ticket.descripcion}


def editar_ticket(solicitud_id, **datos):
    campos = validar_datos_ticket(**datos)
    with SessionLocal() as db:
        # El enlace se bloquea primero, igual que al registrar un servicio.
        vinculo = db.query(TicketEnlace).filter_by(ticket_id=solicitud_id).first()
        if vinculo:
            db.query(EnlaceExterno).filter_by(id=vinculo.enlace_id).with_for_update().first()
        ticket = db.query(Ticket).filter_by(id=solicitud_id).with_for_update().first()
        if ticket is None:
            raise ValueError("La solicitud no existe.")
        tienda = db.query(Tienda).filter_by(sap=str(datos["sap_tienda"]).strip()).first()
        if tienda is None or not tienda.activo:
            raise ValueError("Selecciona una tienda registrada y activa.")
        servicio = db.get(Servicio, ticket.servicio_id) if ticket.servicio_id else None
        # Compatibilidad con servicios anteriores al registro de solicitudes.
        if servicio is None and ticket.numero:
            servicio = servicio_real_ticket(db, ticket.numero)
        if campos["numero"]:
            duplicado = db.query(Ticket).filter(Ticket.numero == campos["numero"], Ticket.id != ticket.id).first()
            otro_servicio = db.query(Servicio).filter(
                func.upper(func.trim(Servicio.ticket)) == campos["numero"],
                Servicio.tipo_registro == "REAL",
                Servicio.id != (servicio.id if servicio else -1)
            ).first()
            if duplicado or otro_servicio:
                raise ValueError("Ese número ya pertenece a otro ticket o servicio.")
        for campo, valor in campos.items():
            setattr(ticket, campo, valor)
        ticket.tienda_id = tienda.id
        if servicio:
            ticket.servicio_id = servicio.id
            servicio.ticket = ticket.numero or "000"
            servicio.tienda_id = tienda.id
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError("Ya existe un ticket con ese número.")


def generar_enlace_ticket(solicitud_id):
    """Permite vincular solicitudes creadas antes de esta función."""
    with SessionLocal() as db:
        ticket = db.query(Ticket).filter_by(id=solicitud_id).with_for_update().first()
        if ticket is None:
            raise ValueError("La solicitud no existe.")
        if db.query(TicketEnlace).filter_by(ticket_id=ticket.id).first():
            return
        validar_ticket_servicio(db, ticket, ticket.tienda_id)
        enlace = EnlaceExterno(token=secrets.token_urlsafe(32), tipo_registro="REAL", estado="PENDIENTE")
        db.add(enlace)
        db.flush()
        db.add(TicketEnlace(ticket_id=ticket.id, enlace_id=enlace.id))
        db.commit()


def actualizar_precio_ticket(solicitud_id, precio):
    from decimal import Decimal, InvalidOperation
    try:
        valor = Decimal(str(precio).strip())
        if not valor.is_finite() or valor < 0 or valor > Decimal("9999999999.99"):
            raise ValueError("Ingresa un precio entre 0 y 9999999999.99.")
        if valor != valor.quantize(Decimal("0.01")):
            raise ValueError("El precio admite como máximo dos decimales.")
    except InvalidOperation:
        raise ValueError("Ingresa un precio válido.")
    with SessionLocal() as db:
        ticket = db.query(Ticket).filter_by(id=solicitud_id).with_for_update().first()
        if ticket is None:
            raise ValueError("La solicitud no existe.")
        ticket.precio = valor
        db.commit()


def eliminar_ticket(solicitud_id):
    with SessionLocal() as db:
        vinculo = db.query(TicketEnlace).filter_by(ticket_id=solicitud_id).first()
        if vinculo:
            enlace = db.query(EnlaceExterno).filter_by(id=vinculo.enlace_id).with_for_update().first()
            if enlace and enlace.estado == "PENDIENTE":
                enlace.estado = "CANCELADO"
        ticket = db.query(Ticket).filter_by(id=solicitud_id).with_for_update().first()
        if ticket is None:
            raise ValueError("La solicitud no existe.")
        if vinculo:
            db.delete(vinculo)
            db.flush()
        db.delete(ticket)
        db.commit()


def obtener_tickets_para_excel():
    tickets = obtener_tickets()
    servicios = {s["servicio_id"]: s for s in obtener_servicios_para_excel()}
    with SessionLocal() as db:
        tiendas = {t.sap: t for t in db.query(Tienda).all()}
        for ticket in tickets:
            servicio = servicios.get(ticket["servicio_id"], {})
            for campo in ("tipo_servicio", "cedula_tecnico", "sap_encargado",
                          "nombre_encargado", "descripcion_falla", "trabajo_realizado",
                          "observaciones", "suministro_repuestos", "repuestos_suministrados"):
                ticket[campo] = servicio.get(campo)
            tienda = tiendas.get(ticket["sap"])
            ticket["departamento"] = tienda.departamento if tienda else None
            ticket["region"] = tienda.region if tienda else None
            ticket["tipo_tienda"] = tienda.tipo if tienda else None
    return tickets
