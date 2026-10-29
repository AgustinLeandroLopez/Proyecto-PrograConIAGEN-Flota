"""Pruebas unitarias de las reglas de alerta con el patrón AAA."""
import unittest

from monitor import esta_en_alerta, obtener_alertas, obtener_estado


class MonitorTest(unittest.TestCase):
    def test_alerta_en_el_limite_de_30_minutos(self):
        for minutos, alerta_esperada in ((29, False), (30, False), (31, True)):
            with self.subTest(minutos=minutos):
                # Arrange: preparar una unidad detenida sin esperar viaje.
                vehiculo = {
                    'velocidad': 0,
                    'minutos_detenido': minutos,
                    'esperando_viaje': False,
                }

                # Act: calcular la alerta y el estado visible.
                alerta = esta_en_alerta(vehiculo)
                estado = obtener_estado(vehiculo)

                # Assert: solo superar los 30 minutos debe generar alerta.
                self.assertEqual(alerta, alerta_esperada)
                if alerta_esperada:
                    self.assertIn('ALERTA', estado)
                else:
                    self.assertIn('dentro del tiempo permitido', estado)

    def test_esperando_viaje_no_genera_alerta_en_el_limite(self):
        for minutos in (29, 30, 31):
            with self.subTest(minutos=minutos):
                # Arrange: preparar una unidad disponible para recibir viaje.
                vehiculo = {
                    'velocidad': 0,
                    'minutos_detenido': minutos,
                    'esperando_viaje': True,
                }

                # Act: calcular la alerta y el estado visible.
                alerta = esta_en_alerta(vehiculo)
                estado = obtener_estado(vehiculo)

                # Assert: la espera de viaje evita la alerta incluso a los 31.
                self.assertFalse(alerta)
                self.assertIn('esperando viaje', estado)

    def test_movimiento_no_genera_alerta_aunque_supere_30_minutos(self):
        # Arrange: preparar una unidad con velocidad positiva.
        vehiculo = {'velocidad': 25, 'minutos_detenido': 31}

        # Act: calcular la alerta y el estado visible.
        alerta = esta_en_alerta(vehiculo)
        estado = obtener_estado(vehiculo)

        # Assert: la velocidad positiva determina que está en movimiento.
        self.assertFalse(alerta)
        self.assertIn('en movimiento', estado)

    def test_obtener_alertas_con_flota_vacia(self):
        # Arrange: preparar una flota sin vehículos.
        vehiculos = []

        # Act: consultar las alertas.
        alertas = obtener_alertas(vehiculos)

        # Assert: no hay alertas ni errores por ausencia de datos.
        self.assertEqual(alertas, [])


if __name__ == '__main__':
    unittest.main()
