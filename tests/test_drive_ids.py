import unittest
from unittest.mock import MagicMock

from googleapiclient.errors import HttpError
from httplib2 import Response

from evidencia_drive import crear_en_drive


class DriveIdsTest(unittest.TestCase):
    def test_reemplazo_se_guarda_antes_de_subir_y_se_reutiliza_tras_timeout(self):
        archivos = MagicMock()
        archivos.get.return_value.execute.side_effect = HttpError(Response({'status': '404'}), b'{}')
        invalido = HttpError(Response({'status': '400'}),
            b'{"error":{"errors":[{"reason":"fileIdNotUsable"}]}}')
        archivos.generateIds.return_value.execute.return_value = {'ids': ['nuevo']}
        estado = {'id': 'anterior', 'parents': ['carpeta'], 'name': '1.pdf'}
        def guardar(nuevo_id):
            estado['id'] = nuevo_id
        intentos = iter([invalido, OSError('timeout'), {'id': 'nuevo'}])
        def ejecutar():
            resultado = next(intentos)
            if archivos.create.call_count > 1:
                self.assertEqual(estado['id'], 'nuevo')
            if isinstance(resultado, Exception):
                raise resultado
            return resultado
        archivos.create.return_value.execute.side_effect = ejecutar
        with self.assertRaises(OSError):
            crear_en_drive(archivos, dict(estado), al_reemplazar_id=guardar)
        self.assertEqual(crear_en_drive(archivos, dict(estado), al_reemplazar_id=guardar), 'nuevo')
        self.assertEqual([c.kwargs['body']['id'] for c in archivos.create.call_args_list],
                         ['anterior', 'nuevo', 'nuevo'])
        self.assertEqual(archivos.generateIds.call_count, 1)

    def test_error_de_permisos_no_regenera_id(self):
        archivos = MagicMock()
        archivos.get.return_value.execute.side_effect = HttpError(Response({'status': '403'}), b'{}')
        with self.assertRaises(HttpError):
            crear_en_drive(archivos, {'id': 'anterior', 'parents': ['carpeta']}, al_reemplazar_id=MagicMock())
        archivos.generateIds.assert_not_called()


if __name__ == '__main__':
    unittest.main()
