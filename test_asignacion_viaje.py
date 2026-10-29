import sqlite3
import json
import threading
from urllib.request import Request, urlopen
from unittest.mock import patch

import acciones_flota
import asistente
import database
import dashboard
import multiagente
from monitor import esta_en_alerta
from skills_flota import invocar
from test_asistente import BaseTemporal
from test_acciones_flota import escritura


class AsignacionViajeTest(BaseTemporal):
    def acuerdo(self):
        with patch('multiagente.gemini_client.generar_json',return_value={'accion':'proponer','vehiculo_id':4,'precio':7000}), \
             patch('multiagente.ollama_client.generar_json',return_value={'accion':'aceptar','vehiculo_id':4,'precio':7000}):
            return asistente.responder({'mensaje':'Negociá el viaje','proveedor':'multiagente'},dashboard.obtener_snapshot)

    def confirmar(self, propuesta, aceptar=True):
        with patch('asistente.interpretar') as nube, patch('asistente.interpretar_local') as local:
            resultado = asistente.responder({'confirmacion':propuesta['propuesta']['token'],'confirmar':aceptar},dashboard.obtener_snapshot)
        nube.assert_not_called()
        local.assert_not_called()
        return resultado

    def test_acuerdo_confirmado_asigna_y_excluye_de_otras_negociaciones(self):
        antes = database.consultar_vehiculo(4)
        acuerdo = self.acuerdo()
        self.assertEqual(acuerdo['estado'],'acuerdo')
        self.assertEqual(database.consultar_vehiculo(4),antes)
        self.assertTrue(any(v['id']==4 for v in multiagente.candidatos_actuales()))
        resultado = self.confirmar(acuerdo)
        self.assertIn('en viaje',resultado)
        actual = database.consultar_vehiculo(4)
        self.assertTrue(actual['en_viaje'])
        self.assertFalse(actual['esperando_viaje'])
        self.assertEqual(actual['velocidad'],antes['velocidad'])
        self.assertEqual(actual['minutos_detenido'],0)
        self.assertFalse(esta_en_alerta(actual))
        self.assertFalse(any(v['id']==4 for v in multiagente.candidatos_actuales()))
        viajes = invocar('consultar_flota', {'operacion':'viajes','patentes':[],'ids':[]})
        self.assertEqual([v['id'] for v in viajes['datos']['vehiculos']],[4])
        database.inicializar_base_de_datos()
        self.assertTrue(database.consultar_vehiculo(4)['en_viaje'])

    def test_cancelar_acuerdo_deja_unidad_disponible(self):
        antes = database.consultar_vehiculo(4)
        self.confirmar(self.acuerdo(),False)
        self.assertEqual(database.consultar_vehiculo(4),antes)
        self.assertEqual(len(multiagente.candidatos_actuales()),1)

    def test_no_repite_asignacion_con_el_mismo_token(self):
        acuerdo = self.acuerdo()
        self.confirmar(acuerdo)
        with self.assertRaisesRegex(ValueError,'procesada'):
            self.confirmar(acuerdo)

    def test_confirmaciones_concurrentes_no_asignan_dos_veces(self):
        primero, segundo = self.acuerdo(),self.acuerdo()
        self.confirmar(primero)
        with self.assertRaisesRegex(ValueError,'cambió'):
            self.confirmar(segundo)

    def test_propuesta_vencida_no_asigna(self):
        acuerdo = self.acuerdo()
        with patch('acciones_flota.time.monotonic',return_value=10**15):
            with self.assertRaisesRegex(ValueError,'venció'):
                self.confirmar(acuerdo)
        self.assertFalse(database.consultar_vehiculo(4)['en_viaje'])

    def test_unidad_modificada_antes_de_confirmar_no_se_sobrescribe(self):
        acuerdo = self.acuerdo()
        database.actualizar_estado_vehiculo(4,30,0,False)
        with self.assertRaisesRegex(ValueError,'cambió'):
            self.confirmar(acuerdo)
        self.assertFalse(database.consultar_vehiculo(4)['en_viaje'])
        self.assertEqual(database.consultar_vehiculo(4)['velocidad'],30)

    def test_cambio_entre_revalidacion_y_propuesta_cancela_token(self):
        real = multiagente.invocar
        def intervenir(nombre, argumentos):
            if nombre == 'gestionar_vehiculos':
                database.actualizar_estado_vehiculo(4,10,0,False)
            return real(nombre,argumentos)
        with patch('multiagente.invocar',side_effect=intervenir):
            resultado = self.acuerdo()
        self.assertEqual(resultado['estado'],'flota_cambio')
        self.assertNotIn('propuesta',resultado)
        self.assertFalse(acciones_flota.PENDIENTES)

    def test_volver_a_esperar_finaliza_viaje_sin_inventar_velocidad(self):
        self.confirmar(self.acuerdo())
        interpretacion = escritura('actualizar',ids=[4],esperando_viaje=True)
        with patch('asistente.interpretar',return_value=interpretacion):
            propuesta = asistente.responder({'mensaje':'Dejá WAIT123 esperando viaje'},dashboard.obtener_snapshot)
        self.confirmar(propuesta)
        actual = database.consultar_vehiculo(4)
        self.assertFalse(actual['en_viaje'])
        self.assertTrue(actual['esperando_viaje'])
        self.assertEqual(len(multiagente.candidatos_actuales()),1)

    def test_velocidad_positiva_conserva_viaje_y_alertas_siguen_vigentes(self):
        self.confirmar(self.acuerdo())
        database.actualizar_estado_vehiculo(4,50,0,False)
        self.assertTrue(database.consultar_vehiculo(4)['en_viaje'])
        database.actualizar_estado_vehiculo(4,0,31,False)
        self.assertTrue(esta_en_alerta(database.consultar_vehiculo(4)))

    def test_estados_incompatibles_rechazados_en_chat_y_sqlite(self):
        with self.assertRaises(ValueError):
            acciones_flota.validar_campos(dict.fromkeys(acciones_flota.CAMPOS) | {'en_viaje':True,'esperando_viaje':True})
        with self.assertRaises(sqlite3.IntegrityError), database.conectar() as conexion:
            conexion.execute('UPDATE vehiculos SET en_viaje=1 WHERE id=4')

    def test_api_acuerdo_confirmacion_y_estado_persistido(self):
        servidor = dashboard.ThreadingHTTPServer((dashboard.HOST,0),dashboard.DashboardHandler)
        puerto = servidor.server_address[1]
        hilo = threading.Thread(target=servidor.serve_forever,daemon=True)
        with patch.object(dashboard,'PORT',puerto):
            hilo.start()
            try:
                base = f'http://127.0.0.1:{puerto}'
                def enviar(datos):
                    with urlopen(Request(base+'/api/asistente',data=json.dumps(datos).encode(),headers={'Content-Type':'application/json'})) as respuesta:
                        return json.load(respuesta)
                with patch('multiagente.gemini_client.generar_json',return_value={'accion':'proponer','vehiculo_id':4,'precio':7000}), \
                     patch('multiagente.ollama_client.generar_json',return_value={'accion':'aceptar','vehiculo_id':4,'precio':7000}):
                    propuesta = enviar({'mensaje':'Negociá el viaje','proveedor':'multiagente'})
                self.assertIn('propuesta',propuesta)
                self.assertFalse(database.consultar_vehiculo(4)['en_viaje'])
                enviar({'confirmacion':propuesta['propuesta']['token'],'confirmar':True})
                with urlopen(base+'/api/vehiculos') as respuesta:
                    unidad = next(v for v in json.load(respuesta)['vehiculos'] if v['id']==4)
                self.assertTrue(unidad['en_viaje'])
                self.assertIn('en viaje',unidad['estado'])
                with urlopen(base+'/api/escenario-negociacion') as respuesta:
                    self.assertEqual(json.load(respuesta)['candidatos'],[])
            finally:
                servidor.shutdown()
                servidor.server_close()
                hilo.join()


if __name__ == '__main__':
    import unittest
    unittest.main()
