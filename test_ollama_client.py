import io
import json
import unittest
import threading
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import asistente
import database
import dashboard
import ollama_client
from errores_asistente import ErrorAsistente
from test_asistente import BaseTemporal, plan
from test_acciones_flota import escritura


class OllamaTransporteTest(unittest.TestCase):
    def test_ejemplos_locales_respetan_contrato_compartido(self):
        for mensaje in ollama_client.ejemplos():
            if mensaje['role'] == 'assistant':
                asistente.validar_alcance(json.loads(mensaje['content']))

    def respuesta(self, contenido=None, **extra):
        return json.dumps({'done': True, 'done_reason': 'stop',
                           'message': {'content': json.dumps(contenido or plan('resumen'))}, **extra}).encode()

    def test_solicitud_local_sin_claves_con_formato_y_workflows(self):
        with patch('ollama_client.build_opener') as construir:
            abrir = construir.return_value.open
            abrir.return_value.__enter__.return_value = io.BytesIO(self.respuesta())
            self.assertEqual(ollama_client.interpretar('resumen', [], {}), plan('resumen'))
        req = abrir.call_args.args[0]
        self.assertEqual(req.full_url, 'http://127.0.0.1:11434/api/chat')
        self.assertNotIn('X-goog-api-key', req.headers)
        payload = json.loads(req.data)
        self.assertEqual(payload['model'], 'gemma3:4b')
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['options']['temperature'], 0)
        self.assertEqual(payload['format']['properties']['cambios']['properties']['velocidad']['type'], ['number', 'null'])
        self.assertFalse(payload['format']['additionalProperties'])
        self.assertIn('gestionar_vehiculos', payload['messages'][0]['content'])
        self.assertEqual(abrir.call_args.kwargs['timeout'], 120)
        # No usa proxy del entorno ni permite redirecciones a otro destino.
        self.assertEqual(construir.call_args.args[0].proxies, {})
        self.assertIsInstance(construir.call_args.args[1], ollama_client.SinRedireccion)
        self.assertIsNone(ollama_client.SinRedireccion().redirect_request(None, None, 302, '', {}, 'https://example.invalid'))

    def test_errores_controlados_sin_reintento_ni_cambio_a_nube(self):
        for error in (URLError('private-details'), TimeoutError(),
                      HTTPError('http://local', 404, 'private-details', {}, None),
                      HTTPError('http://local', 500, 'private-details', {}, None)):
            with self.subTest(error=type(error)), patch('ollama_client.build_opener') as construir:
                construir.return_value.open.side_effect = error
                with self.assertRaises(ErrorAsistente) as caught:
                    ollama_client.interpretar('resumen', [], {})
                self.assertNotIn('private-details', str(caught.exception))
                self.assertEqual(construir.return_value.open.call_count, 1)

    def test_salida_incompleta_o_malformada_no_llega_a_skills(self):
        for raw in (b'{}', b'invalid', b'x' * 32769,
                    self.respuesta(done_reason='length'), self.respuesta(done=False)):
            with self.subTest(raw=raw[:30]), patch('ollama_client.build_opener') as construir:
                construir.return_value.open.return_value.__enter__.return_value = io.BytesIO(raw)
                with self.assertRaises(ErrorAsistente):
                    ollama_client.interpretar('resumen', [], {})

    def test_contexto_excesivo_se_rechaza_antes_de_conectar(self):
        with patch('ollama_client.build_opener') as construir:
            with self.assertRaisesRegex(ErrorAsistente, 'tamaño'):
                ollama_client.interpretar('x' * 20000, [], {})
            construir.assert_not_called()


class ProveedorTest(BaseTemporal):
    def test_local_no_invoca_gemini_y_usa_mismas_skills(self):
        with patch('asistente.interpretar') as nube, patch('asistente.interpretar_local', return_value=plan('alertas')) as local:
            respuesta = asistente.responder({'mensaje': 'alertas', 'proveedor': 'local'}, dashboard.obtener_snapshot)
            self.assertIn('ABC123', respuesta)
            nube.assert_not_called()
            self.assertEqual(local.call_count, 1)

    def test_por_defecto_conserva_nube(self):
        with patch('asistente.interpretar', return_value=plan('resumen')) as nube, patch('asistente.interpretar_local') as local:
            asistente.responder({'mensaje': 'resumen'}, dashboard.obtener_snapshot)
            nube.assert_called_once()
            local.assert_not_called()

    def test_local_no_recurre_a_nube_ante_error(self):
        with patch('asistente.interpretar') as nube, patch('asistente.interpretar_local', side_effect=ErrorAsistente('Ollama no disponible')):
            with self.assertRaises(ErrorAsistente):
                asistente.responder({'mensaje': 'resumen', 'proveedor': 'local'}, dashboard.obtener_snapshot)
            nube.assert_not_called()

    def test_local_propone_y_confirma_sin_volver_a_ningun_modelo(self):
        with patch('asistente.interpretar') as nube, patch('asistente.interpretar_local', return_value=escritura('actualizar', ids=[1], velocidad=45)) as local:
            propuesta = asistente.responder({'mensaje': 'unidad 1 a 45', 'proveedor': 'local'}, dashboard.obtener_snapshot)
            self.assertEqual(database.consultar_vehiculo(1)['velocidad'], 0)
            respuesta = asistente.responder({'confirmacion': propuesta['propuesta']['token'], 'confirmar': True}, dashboard.obtener_snapshot)
            self.assertIn('verificado', respuesta)
            self.assertEqual(database.consultar_vehiculo(1)['velocidad'], 45)
            self.assertEqual(local.call_count, 1)
            nube.assert_not_called()

    def test_local_rechaza_fuera_de_alcance_y_planes_invalidos(self):
        with patch('asistente.interpretar_local', return_value=plan('fuera_de_alcance')):
            self.assertEqual(asistente.responder({'mensaje': 'Boca', 'proveedor': 'local'}, dashboard.obtener_snapshot), asistente.FUERA_DE_ALCANCE)
        with patch('asistente.interpretar_local', return_value=plan('eliminar', skill='consultar_flota')):
            with self.assertRaises(ErrorAsistente):
                asistente.responder({'mensaje': 'elimina 1', 'proveedor': 'local'}, dashboard.obtener_snapshot)
        self.assertIsNotNone(database.consultar_vehiculo(1))

    def test_proveedor_arbitrario_no_es_aceptado(self):
        for proveedor in ('https://example.invalid', '', None, {}):
            with self.subTest(proveedor=proveedor), self.assertRaises(ValueError):
                asistente.validar_entrada({'mensaje': 'resumen', 'proveedor': proveedor})

    def test_http_selector_y_enrutamiento_local(self):
        server = dashboard.ThreadingHTTPServer((dashboard.HOST, 0), dashboard.DashboardHandler)
        port = server.server_address[1]
        with patch.object(dashboard, 'PORT', port):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f'http://127.0.0.1:{port}'
                with urlopen(base) as respuesta:
                    html = respuesta.read().decode('utf-8')
                    self.assertIn('Asistente IA en la nube', html)
                    self.assertIn('Asistente IA local', html)
                    self.assertIn('id="chat-messages-local"', html)
                    self.assertIn('id="chat-messages-nube"', html)
                def enviar(proveedor):
                    return urlopen(Request(base + '/api/asistente',
                        data=json.dumps({'mensaje': 'resumen', 'proveedor': proveedor}).encode(),
                        headers={'Content-Type': 'application/json'}))
                with patch('asistente.interpretar') as nube, patch('asistente.interpretar_local', return_value=plan('resumen')):
                    with enviar('local') as respuesta:
                        self.assertIn('4 vehículos', json.load(respuesta)['respuesta'])
                    nube.assert_not_called()
                with patch('asistente.interpretar') as nube, patch('asistente.interpretar_local', side_effect=ErrorAsistente('Ollama no disponible')):
                    with self.assertRaises(HTTPError) as error:
                        enviar('local')
                    self.assertEqual(error.exception.code, 503)
                    nube.assert_not_called()
                with self.assertRaises(HTTPError) as error:
                    enviar('otro')
                self.assertEqual(error.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
