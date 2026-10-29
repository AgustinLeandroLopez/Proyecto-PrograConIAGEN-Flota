import json
import threading
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import acciones_flota
import asistente
import database
import dashboard
from gemini_client import ErrorGemini
from test_asistente import BaseTemporal, plan


def escritura(operacion, objetivo=None, ids=None, **campos):
    return plan(operacion, pide_modificar=True, patentes=[objetivo] if objetivo else [],
                ids=ids or [], cambios=dict.fromkeys(acciones_flota.CAMPOS) | campos)


class AccionesTest(BaseTemporal):
    def test_activar_espera_desde_chat_en_ambos_modos_solo_tras_confirmar(self):
        for proveedor, identificador in (("nube", 2), ("local", 1)):
            with self.subTest(proveedor=proveedor):
                antes = database.consultar_vehiculo(identificador)
                # Incluso si el modelo omite velocidad, activar espera propone detener.
                interpretacion = escritura('actualizar', ids=[identificador], esperando_viaje=True)
                with patch('asistente.interpretar', return_value=interpretacion) as nube, \
                     patch('asistente.interpretar_local', return_value=interpretacion) as local:
                    propuesta = asistente.responder({
                        'mensaje': f'¿Podés poner la unidad {identificador} en Esperando viaje?',
                        'proveedor': proveedor,
                    }, dashboard.obtener_snapshot)
                    self.assertEqual(propuesta['estado'], 'pendiente_confirmacion')
                    self.assertEqual(database.consultar_vehiculo(identificador), antes)
                    self.assertIn('esperando viaje: sí', propuesta['respuesta'])
                    self.confirmar(propuesta)
                    self.assertEqual(nube.call_count, int(proveedor == 'nube'))
                    self.assertEqual(local.call_count, int(proveedor == 'local'))
                despues = database.consultar_vehiculo(identificador)
                self.assertTrue(despues['esperando_viaje'])
                self.assertEqual(despues['velocidad'], 0)
                self.assertEqual(despues['minutos_detenido'], antes['minutos_detenido'])
                estado = next(v for v in dashboard.obtener_snapshot()['vehiculos'] if v['id'] == identificador)
                self.assertFalse(estado['alerta'])

    def test_espera_sin_identificar_vehiculo_pide_detalles_y_no_escribe(self):
        antes = database.consultar_vehiculos()
        for proveedor in ('nube', 'local'):
            with self.subTest(proveedor=proveedor), \
                 patch('asistente.interpretar', return_value=plan('modificacion')), \
                 patch('asistente.interpretar_local', return_value=plan('modificacion')):
                respuesta = asistente.responder({
                    'mensaje': 'No podes actualizar un vehiculo a "Esperando viaje"',
                    'proveedor': proveedor,
                }, dashboard.obtener_snapshot)
            self.assertIn('patente', respuesta)
            self.assertIn('Esperando viaje', respuesta)
            self.assertNotEqual(respuesta, asistente.FUERA_DE_ALCANCE)
            self.assertFalse(acciones_flota.PENDIENTES)
        self.assertEqual(database.consultar_vehiculos(), antes)

    def test_cancelar_espera_conserva_movimiento(self):
        # Arrange: preparar una propuesta sobre una unidad en movimiento.
        antes = database.consultar_vehiculo(2)
        propuesta = self.proponer(escritura('actualizar', ids=[2], esperando_viaje=True))

        # Act: cancelar la propuesta.
        self.confirmar(propuesta, False)

        # Assert: conservar todos los datos originales.
        self.assertEqual(database.consultar_vehiculo(2), antes)

    def proponer(self, resultado):
        with patch('asistente.interpretar', return_value=resultado):
            return asistente.responder({'mensaje': 'Pedido de flota'}, dashboard.obtener_snapshot)

    def confirmar(self, propuesta, confirmar=True):
        with patch('asistente.interpretar') as modelo:
            respuesta = asistente.responder({
                'confirmacion': propuesta['propuesta']['token'], 'confirmar': confirmar,
            }, dashboard.obtener_snapshot)
            modelo.assert_not_called()
            return respuesta

    def test_alta_solo_al_confirmar_y_no_repite(self):
        propuesta = self.proponer(escritura('agregar',
            **{'patente': 'new123', 'velocidad': 0, 'minutos_detenido': 90, 'esperando_viaje': True}))
        self.assertEqual(len(database.consultar_vehiculos()), 4)
        self.assertIn('NEW123', propuesta['respuesta'])
        self.assertIn('agregado', self.confirmar(propuesta))
        unidad = database.consultar_vehiculos()[-1]
        self.assertEqual(unidad['patente'], 'NEW123')
        self.assertTrue(unidad['esperando_viaje'])
        self.assertFalse(dashboard.obtener_snapshot()['vehiculos'][-1]['alerta'])
        with self.assertRaisesRegex(ValueError, 'procesada'):
            self.confirmar(propuesta)
        self.assertEqual(len(database.consultar_vehiculos()), 5)

    def test_actualizacion_parcial_conserva_datos_y_desactiva_espera(self):
        unidad = database.consultar_vehiculos()[-1]
        propuesta = self.proponer(escritura('actualizar', 'WAIT123', velocidad=55))
        self.assertEqual(database.consultar_vehiculo(unidad['id']), unidad)
        self.assertIn('Antes:', propuesta['respuesta'])
        self.confirmar(propuesta)
        actual = database.consultar_vehiculo(unidad['id'])
        self.assertEqual(actual['velocidad'], 55)
        self.assertEqual(actual['minutos_detenido'], 90)
        self.assertFalse(actual['esperando_viaje'])

    def test_renombra_patente_y_cancela_eliminacion(self):
        propuesta = self.proponer(escritura('actualizar', ids=[2], **{'patente': 'REN123'}))
        self.confirmar(propuesta)
        self.assertEqual(database.consultar_vehiculo(2)['patente'], 'REN123')
        propuesta = self.proponer(escritura('eliminar', 'REN123'))
        self.assertIn('cancelada', self.confirmar(propuesta, False))
        self.assertIsNotNone(database.consultar_vehiculo(2))
        with self.assertRaises(ValueError):
            self.confirmar(propuesta)

    def test_eliminacion_no_reaparece_al_reiniciar_incluso_flota_vacia(self):
        for vehiculo in database.consultar_vehiculos():
            self.confirmar(self.proponer(escritura('eliminar', ids=[vehiculo['id']])))
        self.assertEqual(database.consultar_vehiculos(), [])
        database.inicializar_base_de_datos()
        self.assertEqual(database.consultar_vehiculos(), [])

    def test_cambio_concurrente_no_se_sobrescribe(self):
        # Arrange: modificar la unidad después de preparar la propuesta.
        propuesta = self.proponer(escritura('actualizar', ids=[1], velocidad=40))
        database.actualizar_estado_vehiculo(1, 20, 0, False)

        # Act: intentar confirmar sobre un estado que ya cambió.
        # assertRaises captura la excepción esperada y comprueba su tipo.
        with self.assertRaises(ValueError) as error:
            self.confirmar(propuesta)

        # Assert: informar el conflicto y conservar el cambio concurrente.
        self.assertIn('cambió', str(error.exception))
        self.assertEqual(database.consultar_vehiculo(1)['velocidad'], 20)

    def test_propuesta_vencida_o_inventada_no_escribe(self):
        propuesta = self.proponer(escritura('eliminar', ids=[1]))
        with patch('acciones_flota.time.monotonic', return_value=float('inf')):
            with self.assertRaisesRegex(ValueError, 'venció'):
                self.confirmar(propuesta)
        with self.assertRaises(ValueError):
            acciones_flota.resolver('token-inventado', True)
        self.assertIsNotNone(database.consultar_vehiculo(1))

    def test_duplicado_entre_propuesta_y_confirmacion_no_escribe(self):
        propuesta = self.proponer(escritura('actualizar', ids=[1], **{'patente': 'DUP123'}))
        database.agregar_vehiculo('DUP123', 0, 0)
        with self.assertRaisesRegex(ValueError, 'patente ya existe'):
            self.confirmar(propuesta)
        self.assertEqual(database.consultar_vehiculo(1)['patente'], 'ABC123')

    def test_datos_incompletos_ambiguos_o_duplicados_no_proponen(self):
        antes = database.consultar_vehiculos()
        planes = [
            escritura('agregar', **{'patente': 'NEW123'}),
            escritura('agregar', **{'patente': 'ABC123', 'velocidad': 0, 'minutos_detenido': 0}),
            escritura('actualizar', ids=[1, 2], velocidad=10),
            escritura('actualizar', ids=[999], velocidad=10),
            escritura('actualizar', 'DEF456', ids=[1], velocidad=10),
            escritura('actualizar', ids=[1]),
            escritura('eliminar'),
            escritura('eliminar', ids=[1], velocidad=10),
        ]
        for resultado in planes:
            with self.subTest(resultado=resultado):
                self.assertIsInstance(self.proponer(resultado), str)
                self.assertEqual(database.consultar_vehiculos(), antes)
        self.assertFalse(acciones_flota.PENDIENTES)

    def test_valores_invalidos_y_planes_fuera_de_alcance_no_escriben(self):
        for campo, valor in [('velocidad', -1), ('velocidad', float('nan')),
                             ('velocidad', float('inf')), ('velocidad', True),
                             ('minutos_detenido', 1.5), ('minutos_detenido', -1),
                             ('esperando_viaje', 'true'), ('patente', 'DROP TABLE;')]:
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ErrorGemini):
                self.proponer(escritura('actualizar', ids=[1], **{campo: valor}))
        with self.assertRaises(ErrorGemini):
            self.proponer(plan('actualizar', ids=[1]))
        with self.assertRaises(ErrorGemini):
            self.proponer(plan('resumen', cambios=dict.fromkeys(acciones_flota.CAMPOS) | {'velocidad': 10}))
        self.assertFalse(acciones_flota.PENDIENTES)

    def test_carga_maxima_y_expiracion_de_propuestas(self):
        with patch.object(acciones_flota, 'MAX_PENDIENTES', 1):
            self.proponer(escritura('eliminar', ids=[1]))
            self.assertIn('demasiadas', self.proponer(escritura('eliminar', ids=[2])))
            with patch('acciones_flota.time.monotonic', return_value=10**15):
                self.assertIsInstance(self.proponer(escritura('eliminar', ids=[2])), dict)
        self.assertEqual(len(acciones_flota.PENDIENTES), 1)


class HTTPAccionesTest(BaseTemporal):
    def test_propuesta_confirmacion_cancelacion_y_replay(self):
        server = dashboard.ThreadingHTTPServer((dashboard.HOST, 0), dashboard.DashboardHandler)
        port = server.server_address[1]
        with patch.object(dashboard, 'PORT', port):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{port}'
            def enviar(body, **headers):
                with urlopen(Request(base + '/api/asistente', data=json.dumps(body).encode(),
                             headers={'Content-Type': 'application/json', **headers})) as response:
                    return json.load(response)
            try:
                with patch('asistente.interpretar', return_value=escritura('actualizar', ids=[1], velocidad=25)):
                    propuesta = enviar({'mensaje': 'Actualizá la unidad 1 a 25 km/h'})
                self.assertEqual(database.consultar_vehiculo(1)['velocidad'], 0)
                confirmacion = {'confirmacion': propuesta['propuesta']['token'], 'confirmar': True}
                with self.assertRaises(HTTPError) as error:
                    enviar(confirmacion, Origin='https://example.invalid')
                self.assertEqual(error.exception.code, 403)
                with patch('asistente.interpretar') as modelo:
                    self.assertIn('verificado', enviar(confirmacion)['respuesta'])
                    modelo.assert_not_called()
                with urlopen(base + '/api/vehiculos') as response:
                    self.assertEqual(json.load(response)['vehiculos'][0]['velocidad'], 25)
                with self.assertRaises(HTTPError) as error:
                    enviar(confirmacion)
                self.assertEqual(error.exception.code, 409)
                with patch('asistente.interpretar', return_value=escritura('eliminar', ids=[1])):
                    propuesta = enviar({'mensaje': 'Eliminá la unidad 1'})
                self.assertIn('cancelada', enviar({'confirmacion': propuesta['propuesta']['token'], 'confirmar': False})['respuesta'])
                for body in ({'confirmacion': 'x', 'confirmar': True},
                             {'confirmacion': 'x' * 43, 'confirmar': 'true'},
                             {'mensaje': 'resumen', 'confirmar': True}):
                    with self.assertRaises(HTTPError) as error:
                        enviar(body)
                    self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
