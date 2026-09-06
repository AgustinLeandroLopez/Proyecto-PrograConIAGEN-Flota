import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from database import consultar_vehiculos, inicializar_base_de_datos
from monitor import LIMITE_MINUTOS_DETENIDO, obtener_estado, esta_en_alerta


HOST = "127.0.0.1"
PORT = 8000
RUTA_DASHBOARD = Path(__file__).with_name("dashboard") / "index.html"


def obtener_snapshot():
    vehiculos = []
    for vehiculo in consultar_vehiculos():
        alerta = esta_en_alerta(vehiculo)
        vehiculos.append(
            {
                **vehiculo,
                "estado": obtener_estado(vehiculo),
                "alerta": alerta,
            }
        )

    return {
        "actualizado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "limite_minutos_detenido": LIMITE_MINUTOS_DETENIDO,
        "resumen": {
            "total": len(vehiculos),
            "en_movimiento": sum(v["velocidad"] > 0 for v in vehiculos),
            "detenidos": sum(v["velocidad"] == 0 for v in vehiculos),
            "alertas": sum(v["alerta"] for v in vehiculos),
        },
        "vehiculos": vehiculos,
    }


class DashboardHandler(BaseHTTPRequestHandler):
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
