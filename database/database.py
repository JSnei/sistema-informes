import os
from dotenv import load_dotenv

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
)

from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func


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
            "La credencial debe estar entre 101-199 "
            "para CEDI o 201-299 para BS Electromecánica."
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
            rol=rol.strip(),
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
            "La credencial debe estar entre 101-199 "
            "para CEDI o 201-299 para BS Electromecánica."
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
        tecnico.rol = rol.strip()

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
    tipo_registro="REAL"
):
    with SessionLocal() as db:


        # ------------------------------------------
        # 1. VERIFICAR EL ENLACE
        # ------------------------------------------

        enlace = (
            db.query(EnlaceExterno)
            .filter(EnlaceExterno.token == token)
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

    