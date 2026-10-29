"""Transporte Gemini sin SDK, herramientas, reintentos ni registro de secretos."""
import json
import os
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from prompt_agente import OPERACIONES, SCHEMA, SYSTEM, instrucciones
from errores_asistente import ErrorAsistente as ErrorGemini

TIMEOUT = 20
MAX_RESPONSE_BYTES = 32768


def interpretar(consulta, historial, datos):
    return generar_json(instrucciones(), SCHEMA, {
        "consulta": consulta, "historial_usuario": historial, "estado_actual": datos,
    })


def generar_json(sistema, esquema, datos):
    """Transporte compartido; cada rol conserva su propio contrato y contexto."""
    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise ErrorGemini("Falta configurar GEMINI_API_KEY en .env o en el entorno del servidor. Consultá el README para habilitar el asistente.")
    modelo = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,100}", modelo):
        raise ErrorGemini("GEMINI_MODEL no es válido. Revisá la configuración del servidor.")
    payload = {
        "systemInstruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(datos, ensure_ascii=False)}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1024,
                             "responseMimeType": "application/json", "responseSchema": esquema},
    }
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": clave}, method="POST",
    )
    try:
        deadline = time.monotonic() + TIMEOUT
        with urlopen(request, timeout=TIMEOUT) as response:
            raw = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError
                chunk = response.read1(min(4096, MAX_RESPONSE_BYTES + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError
        result = json.loads(raw)
        candidate = result["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ValueError
        return json.loads("".join(p["text"] for p in candidate["content"]["parts"]
                                 if "text" in p and not p.get("thought")))
    except HTTPError as error:
        status = error.code
        error.close()
        if status == 429:
            raise ErrorGemini("Gemini alcanzó un límite de uso. Revisá las cuotas en AI Studio e intentá más tarde.") from None
        if status in (400, 401, 403, 404):
            raise ErrorGemini("Gemini rechazó la configuración. Revisá la clave, el modelo y el acceso en AI Studio.") from None
        raise ErrorGemini("Gemini no está disponible. Intentá más tarde.") from None
    except (TimeoutError, socket.timeout):
        raise ErrorGemini("Gemini tardó demasiado en responder. Podés intentar nuevamente.") from None
    except (URLError, OSError):
        raise ErrorGemini("No se pudo conectar con Gemini. Revisá la conexión del servidor.") from None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise ErrorGemini("Gemini no devolvió una respuesta válida. Podés reformular la consulta.") from None
