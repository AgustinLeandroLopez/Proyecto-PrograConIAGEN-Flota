"""Zona y precios: migración, confirmaciones y negociación con SQLite temporal."""
import sqlite3
from unittest.mock import patch

import acciones_flota
import asistente
import database
import dashboard
import multiagente
from escenario_flota import cotizar, validar_solicitud
from errores_asistente import ErrorAsistente
from test_acciones_flota import escritura
from test_asistente import BaseTemporal, plan


class DatosPersistentesTest(BaseTemporal):
    def confirmar(self, propuesta):
        return asistente.responder({'confirmacion': propuesta['propuesta']['token'], 'confirmar': True}, dashboard.obtener_snapshot)

    def proponer(self, **campos):
        with patch('asistente.interpretar', return_value=escritura('actualizar', ids=[1], **campos)):
            return asistente.responder({'mensaje': 'Actualizá la configuración de la unidad 1'}, dashboard.obtener_snapshot)

    def test_migracion_desde_base_anterior_preserva_y_no_reinicia_configuracion(self):
        with database.conectar() as conexion:
            conexion.execute('DROP TABLE vehiculos')
            conexion.execute('CREATE TABLE vehiculos (id INTEGER PRIMARY KEY, patente TEXT UNIQUE, velocidad REAL, minutos_detenido INTEGER, esperando_viaje INTEGER)')
            conexion.execute("INSERT INTO vehiculos VALUES (4,'ANT444',0,85,1)")
        database.inicializar_base_de_datos()
        migrado = database.consultar_vehiculo(4)
        self.assertEqual((migrado['zona'], migrado['tarifa_base'], migrado['precio_minimo']), ('Oeste',4200,3200))
        self.assertTrue(migrado['esperando_viaje'])
        self.assertEqual(migrado['minutos_detenido'],85)
        self.assertEqual(len(database.consultar_vehiculos()),1)
        database.actualizar_estado_vehiculo(4,0,85,True,zona='Sur',tarifa_base=9000,precio_minimo=7000)
        esperado = database.consultar_vehiculo(4)
        database.inicializar_base_de_datos()
        self.assertEqual(database.consultar_vehiculo(4),esperado)

    def test_alta_usa_defaults_persistidos_y_no_depende_del_id(self):
        for patente in ('NUE111','NUE222'):
            v = database.agregar_vehiculo(patente,0,0)
            self.assertEqual((v['zona'],v['tarifa_base'],v['precio_minimo']), ('Centro',4000,3000))
        database.inicializar_base_de_datos()
        self.assertEqual(database.consultar_vehiculos()[-1]['zona'],'Centro')

    def test_chat_confirma_zona_y_precios_en_ambos_modos(self):
        for proveedor, identificador in (('nube',1), ('local',2)):
            with self.subTest(proveedor=proveedor):
                antes = database.consultar_vehiculo(identificador)
                interpretacion = escritura('actualizar',ids=[identificador],zona='Sur',tarifa_base=6500,precio_minimo=4500)
                with patch('asistente.interpretar',return_value=interpretacion), patch('asistente.interpretar_local',return_value=interpretacion):
                    propuesta = asistente.responder({'mensaje': f'Unidad {identificador}: zona Sur, tarifa base 6500, mínimo base 4500', 'proveedor':proveedor},dashboard.obtener_snapshot)
                self.assertEqual(propuesta['estado'],'pendiente_confirmacion')
                self.assertIn('6500',propuesta['respuesta'])
                self.assertEqual(database.consultar_vehiculo(identificador),antes)
                self.confirmar(propuesta)
                despues = database.consultar_vehiculo(identificador)
                self.assertEqual((despues['zona'],despues['tarifa_base'],despues['precio_minimo']),('Sur',6500,4500))
                for campo in ('patente','velocidad','minutos_detenido','esperando_viaje'):
                    self.assertEqual(antes[campo],despues[campo])

    def test_actualizacion_parcial_conserva_configuracion_omitida(self):
        antes = database.consultar_vehiculo(1)
        self.confirmar(self.proponer(zona='Norte'))
        despues = database.consultar_vehiculo(1)
        self.assertEqual(despues, {**antes,'zona':'Norte'})
        self.confirmar(self.proponer(velocidad=50))
        actual = database.consultar_vehiculo(1)
        self.assertEqual((actual['zona'],actual['tarifa_base'],actual['precio_minimo']),('Norte',4000,3000))

    def test_cancelar_no_modifica_configuracion(self):
        antes = database.consultar_vehiculo(1)
        propuesta = self.proponer(zona='Sur')
        asistente.responder({'confirmacion':propuesta['propuesta']['token'],'confirmar':False},dashboard.obtener_snapshot)
        self.assertEqual(database.consultar_vehiculo(1),antes)

    def test_rechaza_zonas_y_precios_invalidos_sin_propuestas(self):
        antes = database.consultar_vehiculo(1)
        for campo, valor in (('zona','Zona inexistente'),('tarifa_base',True),('precio_minimo',1.5),
                             ('tarifa_base',0),('precio_minimo',-1),('tarifa_base',1000001)):
            with self.subTest(campo=campo), self.assertRaises(ErrorAsistente):
                self.proponer(**{campo:valor})
        for cambios in ({'tarifa_base':2000},{'precio_minimo':5000}):
            self.assertIsInstance(self.proponer(**cambios),str)
        self.assertEqual(database.consultar_vehiculo(1),antes)
        self.assertFalse(acciones_flota.PENDIENTES)

    def test_sqlite_impide_minimo_mayor_que_base(self):
        with self.assertRaises(sqlite3.IntegrityError), database.conectar() as conexion:
            conexion.execute('UPDATE vehiculos SET precio_minimo=tarifa_base+1 WHERE id=1')
        self.assertEqual(database.consultar_vehiculo(1)['precio_minimo'],3000)

    def test_configuracion_concurrente_invalida_propuesta(self):
        propuesta = self.proponer(velocidad=20)
        database.actualizar_estado_vehiculo(1,0,45,False,zona='Sur')
        with self.assertRaisesRegex(ValueError,'cambió'):
            self.confirmar(propuesta)
        self.assertEqual(database.consultar_vehiculo(1)['zona'],'Sur')
        self.assertEqual(database.consultar_vehiculo(1)['velocidad'],0)

    def test_consulta_muestra_zona_y_tarifas_guardadas(self):
        with patch('asistente.interpretar', return_value=plan('vehiculos',ids=[1])) as modelo:
            respuesta = asistente.responder({'mensaje':'Qué zona y tarifa tiene la unidad 1'},dashboard.obtener_snapshot)
        self.assertIn('Centro',respuesta)
        self.assertIn('$4000',respuesta)
        self.assertEqual(modelo.call_args.args[2]['vehiculos'][0]['precio_minimo'],3000)

    def test_negociacion_usa_configuracion_guardada(self):
        database.actualizar_estado_vehiculo(4,0,90,True,zona='Norte',tarifa_base=7500,precio_minimo=5500)
        candidato = cotizar(multiagente.candidatos_actuales(), validar_solicitud())[0]
        self.assertEqual(candidato['zona'],'Norte')
        self.assertEqual(candidato['tarifa_base'],7500)
        self.assertEqual(candidato['minimo_base'],5500)
        self.assertEqual(candidato['precio_referencia'],7500+6*800+6*400)
        self.assertEqual(candidato['precio_minimo'],5500+12*300)

    def test_configuracion_cambiada_durante_negociacion_impide_acuerdo(self):
        def aceptar(*args):
            database.actualizar_estado_vehiculo(4,0,90,True,tarifa_base=4300)
            return {'accion':'aceptar','vehiculo_id':4,'precio':7000}
        with patch('multiagente.gemini_client.generar_json',return_value={'accion':'proponer','vehiculo_id':4,'precio':7000}), \
             patch('multiagente.ollama_client.generar_json',side_effect=aceptar):
            resultado = multiagente.negociar('Negociá el viaje',[])
        self.assertEqual(resultado['estado'],'flota_cambio')
        self.assertIsNone(resultado['precio_acordado'])


if __name__ == '__main__':
    import unittest
    unittest.main()
