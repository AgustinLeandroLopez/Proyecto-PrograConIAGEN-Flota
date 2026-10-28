import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from configuracion import cargar_configuracion


class ConfiguracionTest(unittest.TestCase):
    def test_carga_solo_gemini_sin_ejecutar_ni_expandir(self):
        with tempfile.TemporaryDirectory() as carpeta, patch.dict(os.environ, {}, clear=True):
            ruta = Path(carpeta) / '.env'
            ruta.write_text(
                '\ufeff# Configuración\nGEMINI_API_KEY="clave=ficticia"\n'
                "GEMINI_MODEL='modelo'\nOTRA_VARIABLE=no\nLINEA_INVALIDA\n",
                encoding='utf-8',
            )
            cargar_configuracion(ruta)
            self.assertEqual(dict(os.environ), {
                'GEMINI_API_KEY': 'clave=ficticia', 'GEMINI_MODEL': 'modelo',
            })

    def test_entorno_tiene_prioridad_y_valores_vacios_se_omiten(self):
        with tempfile.TemporaryDirectory() as carpeta, patch.dict(
            os.environ, {'GEMINI_API_KEY': 'del-entorno'}, clear=True
        ):
            ruta = Path(carpeta) / '.env'
            ruta.write_text('GEMINI_API_KEY=del-archivo\nGEMINI_MODEL=\n', encoding='utf-8')
            cargar_configuracion(ruta)
            self.assertEqual(os.environ['GEMINI_API_KEY'], 'del-entorno')
            self.assertNotIn('GEMINI_MODEL', os.environ)

    def test_archivo_ausente_es_opcional(self):
        with tempfile.TemporaryDirectory() as carpeta:
            cargar_configuracion(Path(carpeta) / '.env')


if __name__ == '__main__':
    unittest.main()
