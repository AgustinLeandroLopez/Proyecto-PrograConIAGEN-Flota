import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from asistente import responder, validar_entrada
from errores_asistente import ErrorAsistente
from configuracion import cargar_configuracion

from database import inicializar_base_de_datos
from skills_flota.herramientas import obtener_snapshot


HOST = "127.0.0.1"
PORT = 8000
RUTA_DASHBOARD = Path(__file__).with_name("dashboard") / "index.html"
CHAT_LOCK = threading.Lock()
MAX_BODY = 24000


class DashboardHandler(BaseHTTPRequestHandler):
    def responder_json(self, status, datos):
        contenido = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def do_POST(self):
        if urlparse(self.path).path != "/api/asistente":
            self.responder_json(404, {"error": "Recurso no encontrado"})
            return
        # Solo JSON del mismo origen local. No se habilita CORS.
        origen = self.headers.get("Origin")
        if (self.headers.get("Host") not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")
                or (origen and origen not in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"))):
            self.responder_json(403, {"error": "Origen no permitido"})
            return
        if self.headers.get_content_type() != "application/json":
            self.responder_json(415, {"error": "La consulta debe enviarse como JSON."})
            return
        try:
            longitud = int(self.headers.get("Content-Length", "0"))
            if not 1 <= longitud <= MAX_BODY or self.headers.get("Transfer-Encoding"):
                raise ValueError("La consulta supera el tamaño admitido o está vacía.")
            self.connection.settimeout(5)
            body = json.loads(self.rfile.read(longitud))
            validar_entrada(body)
        except (ValueError, UnicodeError, OSError):
            self.responder_json(400, {"error": "Consulta inválida. Usá hasta 1000 caracteres y cuatro mensajes de historial."})
            return
        if not CHAT_LOCK.acquire(blocking=False):
            self.responder_json(429, {"error": "Ya hay una consulta en curso. Esperá a que termine."})
            return
        try:
            respuesta = responder(body, obtener_snapshot)
            self.responder_json(200, respuesta if isinstance(respuesta, dict) else {"respuesta": respuesta})
        except ValueError as error:
            self.responder_json(409, {"error": str(error)})
        except ErrorAsistente as error:
            self.responder_json(503, {"error": str(error)})
        except Exception:
            self.responder_json(500, {"error": "No se pudo completar la consulta del asistente."})
        finally:
            CHAT_LOCK.release()

    def do_GET(self):
        ruta = urlparse(self.path).path

        if ruta in ("/", "/index.html"):
            self.responder_archivo(RUTA_DASHBOARD, "text/html; charset=utf-8")
            return

        if ruta == "/api/vehiculos":
            contenido = json.dumps(obtener_snapshot(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)
            return

        self.send_error(404, "Recurso no encontrado")

    def responder_archivo(self, ruta, tipo_contenido):
        try:
            contenido = ruta.read_bytes()
        except FileNotFoundError:
            self.send_error(500, "No se encontró la interfaz del dashboard")
            return

        self.send_response(200)
        self.send_header("Content-Type", tipo_contenido)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def log_message(self, formato, *args):
        print(f"[dashboard] {self.address_string()} - {formato % args}")


def main():
    cargar_configuracion()
    inicializar_base_de_datos()
    servidor = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Dashboard disponible en http://{HOST}:{PORT}")
    print("Presioná Ctrl+C para detenerlo.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard detenido.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
