"""Exportación de tickets con el generador XLSX existente de la aplicación."""
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from database.database import obtener_tickets_para_excel

NOMBRE_ARCHIVO = "Software V2.xlsx"
COLUMNAS = [
    ("id", "Solicitud"), ("numero", "Ticket"), ("estado", "Estado"),
    ("precio", "Precio"), ("estado_precio", "Estado del precio"),
    ("prioridad", "Prioridad"), ("fecha_reporte", "Fecha del reporte"),
    ("fecha_creacion", "Fecha de creación"), ("sap", "SAP tienda"),
    ("tienda", "Tienda"), ("direccion", "Dirección"), ("ciudad", "Ciudad"),
    ("departamento", "Departamento"), ("region", "Región"),
    ("tipo_tienda", "Tipo de tienda"), ("contacto", "Contacto"),
    ("telefonos", "Teléfonos"), ("registrado_por", "Registrado por"),
    ("coordinador", "Coordinador"), ("codigo", "Código"),
    ("equipo", "Equipo"), ("descripcion", "Descripción de la solicitud"),
    ("servicio_id", "Servicio"), ("fecha_realizado", "Fecha de realización"),
    ("tipo_servicio", "Tipo de servicio"), ("cedula_tecnico", "Cédula del técnico"),
    ("tecnico", "Nombre del técnico"), ("telefono_tecnico", "Teléfono del técnico"),
    ("sap_encargado", "SAP del encargado"), ("nombre_encargado", "Encargado"),
    ("descripcion_falla", "Descripción de la falla"),
    ("trabajo_realizado", "Trabajo realizado"), ("observaciones", "Observaciones"),
    ("suministro_repuestos", "Suministró repuestos"),
    ("repuestos_suministrados", "Repuestos suministrados"),
]


def generar_excel_tickets():
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Tickets"
    hoja.append([titulo for _, titulo in COLUMNAS])
    for celda in hoja[1]:
        celda.fill = PatternFill("solid", fgColor="17365D")
        celda.font = Font(color="FFFFFF", bold=True)
        celda.alignment = Alignment(wrap_text=True, vertical="center")
    hoja.row_dimensions[1].height = 34

    for ticket in obtener_tickets_para_excel():
        valores = dict(ticket, estado_precio="Falta precio" if ticket.get("precio") is None else "Con precio")
        fila = hoja.max_row + 1
        color = "C6EFCE" if ticket["estado"] == "REALIZADO" else "FCE4D6"
        for columna, (campo, _) in enumerate(COLUMNAS, 1):
            valor = valores.get(campo)
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                valor = "xxxxx"
            if isinstance(valor, datetime):
                valor = valor.replace(tzinfo=None)
            celda = hoja.cell(fila, columna, valor)
            # Los textos introducidos por usuarios nunca se interpretan como fórmulas.
            if isinstance(valor, str):
                celda.data_type = "s"
            celda.fill = PatternFill("solid", fgColor=color)
            celda.alignment = Alignment(wrap_text=True, vertical="top")
            if isinstance(valor, datetime):
                celda.number_format = "yyyy-mm-dd hh:mm:ss"
            elif campo == "precio" and valor != "xxxxx":
                celda.number_format = '#,##0.00'
        hoja.row_dimensions[fila].height = 60

    hoja.freeze_panes = "D2"
    hoja.auto_filter.ref = hoja.dimensions
    for columna, (campo, titulo) in enumerate(COLUMNAS, 1):
        ancho = 48 if campo in {"descripcion", "descripcion_falla", "trabajo_realizado", "observaciones", "repuestos_suministrados"} else max(18, min(len(titulo) + 4, 30))
        hoja.column_dimensions[get_column_letter(columna)].width = ancho
    hoja.sheet_view.showGridLines = False
    archivo = BytesIO()
    libro.save(archivo)
    archivo.seek(0)
    return archivo
