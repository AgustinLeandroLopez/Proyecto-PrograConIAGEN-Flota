import io
import json
import threading
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import acciones_flota
import asistente
import database
import dashboard
import gemini_client
import multiagente
import ollama_client
from escenario_flota import validar_solicitud
from errores_asistente import ErrorAsistente
from test_asistente import BaseTemporal


def decision(accion, unidad=None, precio=7000):
    return {"accion": accion, "vehiculo_id": unidad,
            "precio": precio if accion in ('proponer', 'aceptar') else None}


class NegociacionTest(BaseTemporal):
    def setUp(self):
        super().setUp()
        self.espera = database.consultar_vehiculos()[-1]["id"]
        self.antes = database.consultar_vehiculos()

    def tearDown(self):
        # Negociar puede preparar una propuesta, pero nunca escribe sin confirmar.
        self.assertEqual(database.consultar_vehiculos(), self.antes)
        super().tearDown()

    def negociar(self):
        return asistente.responder({"mensaje": "Buscá un vehículo para un viaje",
                                   "proveedor": "multiagente", "historial": ["Buscá disponibilidad"]},
                                  dashboard.obtener_snapshot)

    def test_acuerdo_con_roles_contextos_y_skill_compartida(self):
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)) as nube, \
             patch('multiagente.ollama_client.generar_json', return_value=decision('aceptar', self.espera)) as local, \
             patch('multiagente.invocar', wraps=multiagente.invocar) as skill:
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'acuerdo')
        self.assertEqual(resultado['vehiculo_recomendado']['id'], self.espera)
        self.assertEqual(len(resultado['dialogo']), 2)
        self.assertIn('propuesta', resultado)
        self.assertEqual(skill.call_count, 3)  # consulta, revalidación y propuesta de asignación
        self.assertEqual(skill.call_args.args[0], 'gestionar_vehiculos')
        self.assertIn('coordinador', nube.call_args.args[0])
        self.assertIn('responsable', local.call_args.args[0])
        self.assertEqual(nube.call_args.args[2]['historial_usuario'], ['Buscá disponibilidad'])
        self.assertEqual(local.call_args.args[2]['propuesta_anterior'], {'vehiculo_id': self.espera, 'precio': 7000})
        self.assertEqual(resultado['precio_acordado'], 7000)
        self.assertTrue(resultado['ficticio'])
        self.assertIn('Confirmá el cambio', resultado['respuesta'])

    def test_contrapropuesta_y_aceptacion_en_siguiente_ronda(self):
        database.agregar_vehiculo('WAIT222', 0, 20, True)
        self.antes = database.consultar_vehiculos()
        otra = next(v['id'] for v in self.antes if v['patente'] == 'WAIT222')
        with patch('multiagente.gemini_client.generar_json', side_effect=[decision('proponer', otra), decision('aceptar', self.espera)]) as nube, \
             patch('multiagente.ollama_client.generar_json', return_value=decision('proponer', self.espera)) as local:
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'acuerdo')
        self.assertEqual(nube.call_count, 2)
        self.assertEqual(local.call_count, 1)
        self.assertIn('Contrapropongo', resultado['respuesta'])
        self.assertEqual(resultado['dialogo'][-1]['ronda'], 2)

    def test_seleccion_con_multiples_unidades(self):
        database.agregar_vehiculo('WAIT222', 0, 90, True)
        self.antes = database.consultar_vehiculos()
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)), \
             patch('multiagente.ollama_client.generar_json', return_value=decision('aceptar', self.espera)):
            self.assertEqual(self.negociar()['estado'], 'acuerdo')

    def test_no_hay_candidatos_no_llama_proveedores(self):
        with patch('multiagente.candidatos_actuales', return_value=[]), \
             patch('multiagente.gemini_client.generar_json') as nube, \
             patch('multiagente.ollama_client.generar_json') as local:
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'sin_candidatos')
        self.assertIsNone(resultado['vehiculo_recomendado'])
        nube.assert_not_called()
        local.assert_not_called()

    def test_solo_incluye_unidades_en_espera(self):
        candidatos = multiagente.candidatos_actuales()
        self.assertEqual([v['id'] for v in candidatos], [self.espera])

    def test_limite_tres_rondas_sin_fabricar_acuerdo(self):
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)) as nube, \
             patch('multiagente.ollama_client.generar_json', return_value=decision('proponer', self.espera)) as local:
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'sin_acuerdo')
        self.assertIsNone(resultado['vehiculo_recomendado'])
        self.assertEqual(len(resultado['dialogo']), 6)
        self.assertEqual(nube.call_count, 3)
        self.assertEqual(local.call_count, 3)

    def test_rechaza_decisiones_invalidas_sin_invocar_otro_modelo(self):
        for salida in (None, [], {}, decision('eliminar', self.espera), decision('proponer', 999),
                       decision('proponer', 1), decision('proponer', True), decision('proponer', 4.0),
                       decision('aceptar', self.espera), decision('no_aplica', self.espera),
                       {**decision('proponer', self.espera), 'sql': 'DELETE FROM vehiculos'}):
            with self.subTest(salida=salida), \
                 patch('multiagente.gemini_client.generar_json', return_value=salida), \
                 patch('multiagente.ollama_client.generar_json') as local:
                self.assertEqual(self.negociar()['estado'], 'incompleta')
                local.assert_not_called()

    def test_precio_y_distancia_reemplazan_prioridad_por_espera(self):
        database.agregar_vehiculo('WAIT222', 0, 150, True)
        self.antes = database.consultar_vehiculos()
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)), \
             patch('multiagente.ollama_client.generar_json', return_value=decision('aceptar', self.espera)):
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'acuerdo')
        self.assertEqual(resultado['vehiculo_recomendado']['id'], self.espera)

    def test_aceptacion_de_otra_unidad_se_rechaza(self):
        database.agregar_vehiculo('WAIT222', 0, 150, True)
        self.antes = database.consultar_vehiculos()
        mayor = self.antes[-1]['id']
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)), \
             patch('multiagente.ollama_client.generar_json', return_value=decision('aceptar', mayor)):
            self.assertEqual(self.negociar()['estado'], 'incompleta')

    def test_error_local_conserva_dialogo_y_no_reintenta(self):
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)) as nube, \
             patch('multiagente.ollama_client.generar_json', side_effect=ErrorAsistente('Ollama no disponible')) as local:
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'incompleta')
        self.assertEqual(len(resultado['dialogo']), 1)
        self.assertIn('Ollama no disponible', resultado['respuesta'])
        self.assertEqual(nube.call_count, 1)
        self.assertEqual(local.call_count, 1)

    def test_error_nube_no_invoca_ollama(self):
        with patch('multiagente.gemini_client.generar_json', side_effect=ErrorAsistente('Gemini no disponible')), \
             patch('multiagente.ollama_client.generar_json') as local:
            self.assertEqual(self.negociar()['estado'], 'incompleta')
        local.assert_not_called()

    def test_pedido_no_admitido_no_crea_propuestas(self):
        with patch('multiagente.gemini_client.generar_json', return_value=decision('no_aplica')), \
             patch('multiagente.ollama_client.generar_json') as local:
            resultado = asistente.responder({'mensaje': 'Eliminá WAIT123', 'proveedor': 'multiagente'}, dashboard.obtener_snapshot)
        self.assertEqual(resultado['estado'], 'no_aplica')
        local.assert_not_called()

    def test_negociacion_de_precio_con_concesiones(self):
        with patch('multiagente.gemini_client.generar_json', side_effect=[
                decision('proponer', self.espera, 5000), decision('proponer', self.espera, 8000),
                decision('aceptar', self.espera, 8500)]) as nube, \
             patch('multiagente.ollama_client.generar_json', side_effect=[
                decision('proponer', self.espera, 10000), decision('proponer', self.espera, 8500)]) as local:
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'acuerdo')
        self.assertEqual(resultado['precio_acordado'], 8500)
        self.assertEqual([d['precio'] for d in resultado['dialogo']], [5000, 10000, 8000, 8500, 8500])
        self.assertEqual(nube.call_count, 3)
        self.assertEqual(local.call_count, 2)
        self.assertIn('km al retiro', resultado['respuesta'])

    def test_no_acepta_otro_precio_de_la_misma_unidad(self):
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera, 7000)), \
             patch('multiagente.ollama_client.generar_json', return_value=decision('aceptar', self.espera, 8000)):
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'incompleta')
        self.assertIsNone(resultado['precio_acordado'])

    def test_cliente_no_puede_superar_presupuesto(self):
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera, 9500)), \
             patch('multiagente.ollama_client.generar_json') as local:
            resultado = self.negociar()
        self.assertEqual(resultado['estado'], 'incompleta')
        local.assert_not_called()

    def test_flota_no_puede_aceptar_ni_ofrecer_menos_que_minimo(self):
        for accion in ('aceptar', 'proponer'):
            with self.subTest(accion=accion), \
                 patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera, 5000)), \
                 patch('multiagente.ollama_client.generar_json', return_value=decision(accion, self.espera, 5000)):
                resultado = self.negociar()
            self.assertEqual(resultado['estado'], 'incompleta')
            self.assertIsNone(resultado['precio_acordado'])

    def test_cliente_no_acepta_contraoferta_que_supera_presupuesto(self):
        with patch('multiagente.gemini_client.generar_json', side_effect=[
                decision('proponer', self.espera, 7000), decision('aceptar', self.espera, 10000)]), \
             patch('multiagente.ollama_client.generar_json', return_value=decision('proponer', self.espera, 10000)):
            self.assertEqual(self.negociar()['estado'], 'incompleta')

    def test_precios_invalidos_se_rechazan(self):
        for precio in (True, 1.5, 0, -1, None, '7000', float('nan'), 10601):
            with self.subTest(precio=precio), \
                 patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera, precio)), \
                 patch('multiagente.ollama_client.generar_json') as local:
                self.assertEqual(self.negociar()['estado'], 'incompleta')
            local.assert_not_called()

    def test_presupuesto_incompatible_puede_terminar_sin_acuerdo(self):
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera, 1000)), \
             patch('multiagente.ollama_client.generar_json', return_value=decision('retirarse')):
            resultado = multiagente.negociar('Negociá este viaje', [], {
                'origen': 'Centro', 'destino': 'Norte', 'presupuesto': 1000})
        self.assertEqual(resultado['estado'], 'sin_acuerdo')
        self.assertIsNone(resultado['precio_acordado'])
        self.assertEqual(len(resultado['dialogo']), 2)

    def test_contextos_con_limites_distintos(self):
        with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)) as nube, \
             patch('multiagente.ollama_client.generar_json', return_value=decision('aceptar', self.espera)) as local:
            self.negociar()
        comprador, vendedor = nube.call_args.args[2], local.call_args.args[2]
        self.assertEqual(comprador['privado'], {'presupuesto_maximo': 9000})
        self.assertNotIn('presupuesto', vendedor['solicitud'])
        self.assertNotIn('presupuesto_maximo', vendedor['privado'])
        self.assertNotIn('precio_minimo', comprador['candidatos'][0])
        self.assertNotIn('minimo_base', comprador['candidatos'][0])
        self.assertEqual(vendedor['privado']['precios_minimos'][0]['precio_minimo'], 6200)
        self.assertEqual(comprador['dialogo'], [])

    def test_solicitud_estructurada_solo_para_multiagente(self):
        solicitud = validar_solicitud()
        for proveedor in ('nube', 'local'):
            with self.subTest(proveedor=proveedor), self.assertRaises(ValueError):
                asistente.validar_entrada({'mensaje': 'resumen', 'proveedor': proveedor, 'solicitud': solicitud})
        for datos in (None, {}, {**solicitud, 'precio_minimo': 1},
                      {**solicitud, 'presupuesto': True}, {**solicitud, 'presupuesto': 0},
                      {**solicitud, 'presupuesto': 1.5}, {**solicitud, 'presupuesto': 1000001},
                      {**solicitud, 'origen': 'Lugar real'}, {**solicitud, 'destino': 'Centro'}):
            with self.subTest(datos=datos), self.assertRaises(ValueError):
                asistente.validar_entrada({'mensaje': 'Negociá', 'proveedor': 'multiagente', 'solicitud': datos})

    def test_revalida_disponibilidad_antes_de_acuerdo(self):
        inicial = multiagente.candidatos_actuales()
        nueva = [{**inicial[0], 'minutos_detenido': 100}]
        for actual in ([], nueva, [{**inicial[0], 'id': 100}, *inicial]):
            with self.subTest(actual=actual), \
                 patch('multiagente.candidatos_actuales', side_effect=[inicial, actual]), \
                 patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)), \
                 patch('multiagente.ollama_client.generar_json', return_value=decision('aceptar', self.espera)):
                resultado = self.negociar()
            self.assertEqual(resultado['estado'], 'flota_cambio')
            self.assertIsNone(resultado['vehiculo_recomendado'])

    def test_contrato_http_y_flotas_temporales(self):
        server = dashboard.ThreadingHTTPServer((dashboard.HOST, 0), dashboard.DashboardHandler)
        port = server.server_address[1]
        with patch.object(dashboard, 'PORT', port):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f'http://127.0.0.1:{port}'
                with urlopen(base) as response:
                    html = response.read().decode('utf-8')
                self.assertIn('Selección multiagente', html)
                self.assertIn('id="chat-messages-multiagente"', html)
                self.assertIn('id="scenario-budget"', html)
                with urlopen(base + '/api/escenario-negociacion?origen=Norte&destino=Sur') as response:
                    escenario = json.load(response)
                self.assertTrue(escenario['ficticio'])
                self.assertEqual(escenario['candidatos'][0]['km_viaje'], 11)
                for query in ('?origen=Centro&destino=Centro', '?origen=Desconocida',
                              '?origen=Norte&origen=Sur', '?precio_minimo=1'):
                    with self.subTest(query=query), self.assertRaises(HTTPError) as error:
                        urlopen(base + '/api/escenario-negociacion' + query)
                    self.assertEqual(error.exception.code, 400)
                with urlopen(base + '/api/vehiculos') as response:
                    vehiculos = json.load(response)['vehiculos']
                    self.assertEqual(len(vehiculos), 4)
                    self.assertEqual(vehiculos[0]['zona'], 'Centro')
                    self.assertEqual(vehiculos[0]['tarifa_base'], 4000)
                    self.assertEqual(vehiculos[0]['precio_minimo'], 3000)
                with patch('multiagente.gemini_client.generar_json', return_value=decision('proponer', self.espera)), \
                     patch('multiagente.ollama_client.generar_json', return_value=decision('aceptar', self.espera)):
                    request = Request(base + '/api/asistente', data=json.dumps({
                        'mensaje': 'Buscá un vehículo', 'proveedor': 'multiagente',
                        'solicitud': {'origen': 'Centro', 'destino': 'Norte', 'presupuesto': 8500}}).encode(),
                        headers={'Content-Type': 'application/json'})
                    with urlopen(request) as response:
                        resultado = json.load(response)
                    self.assertEqual(resultado['estado'], 'acuerdo')
                    self.assertEqual(resultado['solicitud']['presupuesto'], 8500)
                    self.assertEqual(resultado['precio_acordado'], 7000)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


class TransporteRolesTest(BaseTemporal):
    def test_contratos_especificos_llegan_a_ambos_transportes(self):
        salida = decision('proponer', 4)
        raw = json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {
            'parts': [{'text': json.dumps(salida)}]}}]}).encode()
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'clave-de-prueba'}), patch('gemini_client.urlopen') as abrir:
            abrir.return_value.__enter__.return_value = io.BytesIO(raw)
            self.assertEqual(gemini_client.generar_json('rol de prueba', multiagente.SCHEMA, {'ronda': 1}), salida)
        payload = json.loads(abrir.call_args.args[0].data)
        self.assertEqual(payload['systemInstruction']['parts'][0]['text'], 'rol de prueba')
        self.assertEqual(payload['generationConfig']['responseSchema'], multiagente.SCHEMA)
        raw = json.dumps({'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(salida)}}).encode()
        with patch('ollama_client.build_opener') as construir:
            abrir = construir.return_value.open
            abrir.return_value.__enter__.return_value = io.BytesIO(raw)
            self.assertEqual(ollama_client.generar_json('rol local', multiagente.SCHEMA, {'ronda': 1}), salida)
        payload = json.loads(abrir.call_args.args[0].data)
        self.assertEqual(payload['messages'][0]['content'], 'rol local')
        self.assertEqual(payload['format']['properties']['vehiculo_id']['type'], ['integer', 'null'])
        self.assertEqual(payload['model'], 'gemma3:4b')
        self.assertEqual(abrir.call_args.args[0].full_url, ollama_client.ENDPOINT)

    def test_rol_local_respeta_limite_de_contexto(self):
        with patch('ollama_client.build_opener') as construir:
            with self.assertRaises(ErrorAsistente):
                ollama_client.generar_json('x' * 14001, multiagente.SCHEMA, {})
        construir.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
