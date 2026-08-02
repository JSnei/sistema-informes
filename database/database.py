import sqlite3
from pathlib import Path


# Ruta donde se guardará la base de datos
RUTA_DB = Path(__file__).parent / "sistema.db"


def conectar():
    conexion = sqlite3.connect(RUTA_DB)
    conexion.row_factory = sqlite3.Row
    return conexion


def crear_base_datos():

    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tecnicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credencial TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            rol TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)

    conexion.commit()
    conexion.close()


def obtener_tecnicos():
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT id, credencial, nombre, correo, rol, activo
        FROM tecnicos
        ORDER BY nombre ASC
    """)

    tecnicos = cursor.fetchall()
    conexion.close()

    return tecnicos


def obtener_tecnico(id_tecnico):
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT id, credencial, nombre, correo, rol, activo
        FROM tecnicos
        WHERE id = ?
    """, (id_tecnico,))

    tecnico = cursor.fetchone()
    conexion.close()

    return tecnico


def agregar_tecnico(credencial, nombre, correo, rol):
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        INSERT INTO tecnicos (
            credencial,
            nombre,
            correo,
            rol,
            activo
        )
        VALUES (?, ?, ?, ?, 1)
    """, (
        credencial,
        nombre,
        correo,
        rol
    ))

    conexion.commit()
    conexion.close()


def editar_tecnico(id_tecnico, credencial, nombre, correo, rol):
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        UPDATE tecnicos
        SET credencial = ?,
            nombre = ?,
            correo = ?,
            rol = ?
        WHERE id = ?
    """, (
        credencial,
        nombre,
        correo,
        rol,
        id_tecnico
    ))

    conexion.commit()
    conexion.close()


def cambiar_estado_tecnico(id_tecnico):
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        UPDATE tecnicos
        SET activo =
            CASE
                WHEN activo = 1 THEN 0
                ELSE 1
            END
        WHERE id = ?
    """, (id_tecnico,))

    conexion.commit()
    conexion.close()


def eliminar_tecnico(id_tecnico):
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        DELETE FROM tecnicos
        WHERE id = ?
    """, (id_tecnico,))

    conexion.commit()
    conexion.close()

def obtener_tecnico_por_credencial(credencial):
    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT id, credencial, nombre, correo, rol, activo
        FROM tecnicos
        WHERE credencial = ?
    """, (credencial,))

    tecnico = cursor.fetchone()
    conexion.close()

    return tecnico