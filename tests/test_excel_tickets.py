"""Pruebas del exportador, sin correo, PostgreSQL ni Google Drive."""
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from openpyxl import load_workbook

import excel_tickets


class ExcelTicketsTest(unittest.TestCase):
    def test_datos_colores_y_textos_seguros(self):
        tickets = [
            {"id": 1, "numero": "000", "estado": "PENDIENTE", "precio": None,
             "descripcion": "=HYPERLINK(\"https://example.com\")"},
            {"id": 2, "numero": "00123", "estado": "REALIZADO", "precio": Decimal("0.00"),
             "cedula_tecnico": "001234", "fecha_realizado": datetime(2026, 11, 4)},
        ]
        with patch.object(excel_tickets, "obtener_tickets_para_excel", return_value=tickets):
            archivo = excel_tickets.generar_excel_tickets()
        hoja = load_workbook(archivo).active
        columnas = {campo: indice + 1 for indice, (campo, _) in enumerate(excel_tickets.COLUMNAS)}
        self.assertEqual(hoja.max_row, 3)
        self.assertEqual(hoja.cell(2, columnas["precio"]).value, "xxxxx")
        self.assertEqual(hoja.cell(2, columnas["cedula_tecnico"]).value, "xxxxx")
        self.assertEqual(hoja.cell(2, columnas["estado_precio"]).value, "Falta precio")
        self.assertEqual(hoja.cell(3, columnas["precio"]).value, 0)
        self.assertEqual(hoja.cell(3, columnas["estado_precio"]).value, "Con precio")
        self.assertEqual(hoja.cell(3, columnas["numero"]).value, "00123")
        self.assertEqual(hoja.cell(3, columnas["cedula_tecnico"]).value, "001234")
        self.assertEqual(hoja.cell(2, columnas["descripcion"]).data_type, "s")
        self.assertEqual(hoja["A2"].fill.fgColor.rgb, "00FCE4D6")
        self.assertEqual(hoja["A3"].fill.fgColor.rgb, "00C6EFCE")
        self.assertIsInstance(hoja.cell(3, columnas["fecha_realizado"]).value, datetime)
        self.assertEqual(hoja.freeze_panes, "D2")
        self.assertTrue(hoja.auto_filter.ref)

    def test_sin_tickets(self):
        with patch.object(excel_tickets, "obtener_tickets_para_excel", return_value=[]):
            hoja = load_workbook(excel_tickets.generar_excel_tickets()).active
        self.assertEqual(hoja.max_row, 1)


if __name__ == "__main__":
    unittest.main()
