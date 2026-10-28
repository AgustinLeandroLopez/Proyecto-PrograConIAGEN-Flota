import io
import json
import os
from unittest.mock import patch

from mcp import Client

import acciones_flota
import asistente
import database
import dashboard
import gemini_client
from servidor_mcp import mcp
from skills_flota import catalogo, confirmar, invocar, validar_invocacion
from skills_flota.__main__ import demo
from skills_flota.contratos import SALIDA, validar
from test_asistente import BaseTemporal, plan
from test_servidor_mcp import obtener_resultado_estructurado
import unittest


def cambios(**valores):
    return dict.fromkeys(acciones_flota.CAMPOS) | valores


class SkillsTest(BaseTemporal):
    def test_catalogo_documenta_y_valida_ejemplos_de_las_tres_skills(self):
        habilidades = catalogo()
        self.assertEqual({s['nombre'] for s in habilidades},
                         {'consultar_flota', 'gestionar_vehiculos', 'eliminar_vehiculo'})
        for habilidad in habilidades:
            self.assertTrue(habilidad['workflow'])
            self.assertTrue(habilidad['herramientas'])
            self.assertEqual(habilidad['version'], '1.0.0')
            for ejemplo in habilidad['ejemplos']:
                validar_invocacion(habilidad['nombre'], ejemplo)
            self.assertEqual(habilidad['output_schema'], SALIDA)
        habilidades[0]['input_schema']['properties'].clear()
        self.assertTrue(catalogo()[0]['input_schema']['properties'])

    def test_invocacion_python_completa_sin_modelo(self):
        with patch('gemini_client.interpretar') as modelo:
            propuesta = invocar('gestionar_vehiculos', {
                'operacion': 'agregar', 'patentes': [], 'ids': [],
                'cambios': cambios(patente='SKL123', velocidad=0, minutos_detenido=80, esperando_viaje=True),
            })
            self.assertEqual(propuesta['skill'], 'gestionar_vehiculos')
            self.assertEqual(propuesta['estado'], 'pendiente_confirmacion')
            self.assertEqual(len(database.consultar_vehiculos()), 4)
            alta = confirmar(propuesta['propuesta']['token'], True)
            self.assertEqual(alta['estado'], 'completado')
            consulta = invocar('consultar_flota', {'operacion': 'esperando', 'patentes': ['SKL123'], 'ids': []})
            self.assertEqual(consulta['datos']['vehiculos'][0]['patente'], 'SKL123')
            self.assertFalse(consulta['datos']['vehiculos'][0]['alerta'])
            baja = invocar('eliminar_vehiculo', {
                'operacion': 'eliminar', 'patentes': ['SKL123'], 'ids': [], 'cambios': cambios(),
            })
            resultado = confirmar(baja['propuesta']['token'], True)
            self.assertEqual(resultado['skill'], 'eliminar_vehiculo')
            self.assertTrue(resultado['datos']['eliminado'])
            for resultado in (propuesta, alta, consulta, baja, resultado):
                validar(resultado, SALIDA)
            modelo.assert_not_called()

    def test_contrato_cerrado_y_tipos_invalidos_no_ejecutan(self):
        antes = database.consultar_vehiculos()
        casos = [
            ('consultar_flota', {'operacion': 'eliminar', 'patentes': [], 'ids': []}),
            ('consultar_flota', {'operacion': 'resumen', 'patentes': [], 'ids': [True]}),
            ('consultar_flota', {'operacion': 'resumen', 'patentes': [], 'ids': [], 'canal': 'mcp'}),
            ('gestionar_vehiculos', {'operacion': 'actualizar', 'patentes': [], 'ids': [1], 'cambios': cambios(velocidad=float('inf'))}),
            ('gestionar_vehiculos', {'operacion': 'actualizar', 'patentes': [], 'ids': [1], 'cambios': cambios(minutos_detenido=1.5)}),
            ('gestionar_vehiculos', {'operacion': 'actualizar', 'patentes': [], 'ids': [1], 'cambios': cambios(velocidad=-5)}),
            ('codigo_arbitrario', {}),
        ]
        with patch('acciones_flota.preparar') as ejecutar:
            for nombre, argumentos in casos:
                with self.subTest(nombre=nombre, argumentos=argumentos), self.assertRaises(ValueError):
                    invocar(nombre, argumentos)
            ejecutar.assert_not_called()
        self.assertEqual(database.consultar_vehiculos(), antes)

    def test_error_de_negocio_es_salida_estructurada(self):
        resultado = invocar('eliminar_vehiculo', {
            'operacion': 'eliminar', 'patentes': [], 'ids': [999], 'cambios': cambios(),
        })
        self.assertEqual(resultado['estado'], 'error')
        self.assertEqual(resultado['skill'], 'eliminar_vehiculo')
        self.assertNotIn('propuesta', resultado)
        validar(resultado, SALIDA)

    def test_modificar_resultado_no_altera_la_propuesta_guardada(self):
        propuesta = invocar('gestionar_vehiculos', {
            'operacion': 'actualizar', 'patentes': [], 'ids': [1],
            'cambios': cambios(velocidad=20),
        })
        propuesta['datos']['vehiculo']['velocidad'] = 999
        resultado = confirmar(propuesta['propuesta']['token'], True)
        self.assertEqual(resultado['datos']['vehiculo']['velocidad'], 20)
        self.assertEqual(database.consultar_vehiculo(1)['velocidad'], 20)

    def test_salida_invalida_de_una_skill_se_rechaza(self):
        with patch('skills_flota.consultar.obtener_snapshot', return_value={
            'vehiculos': [{'id': 1, 'patente': 'AAA123', 'velocidad': 0,
                           'minutos_detenido': 0, 'esperando_viaje': False,
                           'alerta': False, 'estado': 'estado', 'extra': 'no permitido'}],
            'limite_minutos_detenido': 30,
        }):
            with self.assertRaises(ValueError):
                invocar('consultar_flota', {'operacion': 'vehiculos', 'patentes': [], 'ids': []})

    def test_agente_rechaza_skill_y_operacion_incompatibles(self):
        for resultado in (plan('resumen', skill='eliminar_vehiculo'),
                          plan('eliminar', skill='consultar_flota', pide_modificar=True, ids=[1]),
                          plan('fuera_de_alcance', skill='consultar_flota')):
            with self.subTest(resultado=resultado), patch('asistente.interpretar', return_value=resultado):
                with self.assertRaises(gemini_client.ErrorGemini):
                    asistente.responder({'mensaje': 'pedido'}, dashboard.obtener_snapshot)
        self.assertIsNotNone(database.consultar_vehiculo(1))

    def test_agente_invoca_registro_y_no_solo_documenta_skills(self):
        with patch('asistente.interpretar', return_value=plan('resumen')), patch('asistente.invocar', wraps=invocar) as registro:
            respuesta = asistente.responder({'mensaje': 'resumen'}, dashboard.obtener_snapshot)
        self.assertIn('4 vehículos', respuesta)
        self.assertEqual(registro.call_args.args, ('consultar_flota', {'operacion': 'resumen', 'patentes': [], 'ids': []}))

    def test_catalogo_y_workflows_se_envian_a_gemini(self):
        raw = json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(plan('resumen'))}]}}]}).encode()
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-secret'}), patch('gemini_client.urlopen') as transporte:
            transporte.return_value.__enter__.return_value = io.BytesIO(raw)
            gemini_client.interpretar('resumen', [], {})
        payload = json.loads(transporte.call_args.args[0].data)
        instrucciones = payload['systemInstruction']['parts'][0]['text']
        for habilidad in catalogo():
            self.assertIn(habilidad['nombre'], instrucciones)
            self.assertIn(habilidad['workflow'][0], instrucciones)
        self.assertNotIn('test-secret', instrucciones)
        self.assertIn('skill', payload['generationConfig']['responseSchema']['required'])

    def test_demo_aislada_conserva_base_del_consumidor(self):
        antes, ruta = database.consultar_vehiculos(), database.RUTA_BASE_DATOS
        resultados = demo()
        self.assertEqual(database.RUTA_BASE_DATOS, ruta)
        self.assertEqual(database.consultar_vehiculos(), antes)
        self.assertEqual({r['skill'] for r in resultados}, {'consultar_flota', 'gestionar_vehiculos', 'eliminar_vehiculo'})
        self.assertEqual(resultados[-1]['datos']['resumen']['total'], 3)


class ReutilizacionMCPTest(unittest.IsolatedAsyncioTestCase):
    async def test_python_y_mcp_comparten_gestion_y_consultas(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as carpeta, patch.object(database, 'RUTA_BASE_DATOS', Path(carpeta) / 'test.db'):
            database.inicializar_base_de_datos()
            propuesta = invocar('gestionar_vehiculos', {
                'operacion': 'agregar', 'patentes': [], 'ids': [],
                'cambios': cambios(patente='REU123', velocidad=0, minutos_detenido=50, esperando_viaje=True),
            })
            alta = confirmar(propuesta['propuesta']['token'], True)
            identificador = alta['datos']['vehiculo']['id']
            async with Client(mcp, raise_exceptions=True) as cliente:
                consulta = await cliente.call_tool('consultar_estado_vehiculo', {'vehiculo_id': identificador})
                self.assertTrue(obtener_resultado_estructurado(consulta)['esperando_viaje'])
                actualizacion = await cliente.call_tool('actualizar_estado_vehiculo', {
                    'vehiculo_id': identificador, 'velocidad': 60, 'minutos_detenido': 0,
                })
                self.assertFalse(actualizacion.is_error)
                lectura = invocar('consultar_flota', {'operacion': 'vehiculos', 'ids': [identificador], 'patentes': []})
                unidad = lectura['datos']['vehiculos'][0]
                self.assertEqual(unidad['velocidad'], 60)
                self.assertFalse(unidad['esperando_viaje'])
                baja = await cliente.call_tool('eliminar_vehiculo', {'vehiculo_id': identificador})
                self.assertFalse(baja.is_error)
                lectura = invocar('consultar_flota', {'operacion': 'vehiculos', 'ids': [identificador], 'patentes': []})
                self.assertEqual(lectura['datos']['vehiculos'], [])


if __name__ == '__main__':
    unittest.main()
