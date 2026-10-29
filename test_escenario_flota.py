import unittest

from escenario_flota import ZONAS, distancia, validar_solicitud, cotizar


def unidad(identificador=4, **cambios):
    return {'id': identificador, 'zona': 'Oeste', 'tarifa_base': 4200, 'precio_minimo': 3200, **cambios}


class EscenarioTest(unittest.TestCase):
    def test_distancias_fijas_simetricas_y_no_negativas(self):
        for origen in ZONAS:
            self.assertEqual(distancia(origen, origen), 0)
            for destino in ZONAS:
                self.assertEqual(distancia(origen, destino), distancia(destino, origen))
                self.assertGreaterEqual(distancia(origen, destino), 0)

    def test_costos_se_calculan_con_ambos_tramos(self):
        # Arrange: preparar una unidad y la ruta ficticia Centro -> Norte.
        unidades = [unidad()]
        solicitud = validar_solicitud()

        # Act: cotizar el retiro y el viaje.
        candidato = cotizar(unidades, solicitud)[0]

        # Assert: verificar distancias y ambos precios contra valores conocidos.
        self.assertEqual(candidato['zona'], 'Oeste')
        self.assertEqual(candidato['km_retiro'], 4)
        self.assertEqual(candidato['km_viaje'], 6)
        self.assertEqual(candidato['precio_referencia'], 4200 + 6 * 800 + 4 * 400)
        self.assertEqual(candidato['precio_minimo'], 3200 + 10 * 300)

    def test_usa_valores_recibidos_independientes_del_id_sin_mutacion(self):
        unidades = [unidad(1), unidad(4, zona='Sur')]
        antes = [dict(v) for v in unidades]
        self.assertEqual(cotizar(unidades, validar_solicitud()), cotizar(list(reversed(unidades)), validar_solicitud()))
        self.assertEqual(unidades, antes)
        self.assertEqual(cotizar([unidad(1)], validar_solicitud())[0]['zona'],
                         cotizar([unidad(5)], validar_solicitud())[0]['zona'])
        distinta = cotizar([unidad(1, zona='Norte', tarifa_base=7000, precio_minimo=5000)], validar_solicitud())[0]
        self.assertEqual(distinta['zona'], 'Norte')
        self.assertEqual(distinta['precio_referencia'], 7000 + 6 * 800 + 6 * 400)

    def test_cambio_de_ruta_recalcula_costos_y_minimos_validos(self):
        for origen in ZONAS:
            for destino in ZONAS:
                if origen == destino:
                    continue
                solicitud = validar_solicitud({'origen': origen, 'destino': destino, 'presupuesto': 9000})
                for candidato in cotizar([unidad(i) for i in range(1, 5)], solicitud):
                    self.assertGreater(candidato['precio_minimo'], 0)
                    self.assertLessEqual(candidato['precio_minimo'], candidato['precio_referencia'])
        norte = cotizar([unidad()], validar_solicitud())[0]
        oeste = cotizar([unidad()], validar_solicitud({'origen': 'Oeste', 'destino': 'Centro', 'presupuesto': 9000}))[0]
        self.assertNotEqual(norte['precio_referencia'], oeste['precio_referencia'])


if __name__ == '__main__':
    unittest.main()
