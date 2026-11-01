"""
RedTutor IA - Backend Flask
---------------------------
Sirve la interfaz web y actúa como intermediario entre el navegador y la API
local de Ollama (http://localhost:11434).

Endpoints:
    GET  /              -> interfaz de chat (templates/index.html)
    GET  /api/health    -> estado de Ollama y de los modelos requeridos
    POST /api/chat      -> conversación con RedTutor (streaming NDJSON)
    POST /api/compare   -> misma pregunta al modelo base y a RedTutor

Configuración por variables de entorno (opcionales):
    OLLAMA_HOST      (por defecto http://localhost:11434)
    REDTUTOR_MODEL   (por defecto redtutor)
    BASE_MODEL       (por defecto llama3.2:3b)
    OLLAMA_TIMEOUT   segundos de espera por respuesta (por defecto 180)
    PORT             puerto de Flask (por defecto 5000)
"""

import json
import os
import re
import time
import unicodedata
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_HOST.startswith("http"):
    OLLAMA_HOST = "http://" + OLLAMA_HOST
REDTUTOR_MODEL = os.getenv("REDTUTOR_MODEL", "redtutor")
BASE_MODEL = os.getenv("BASE_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))
PORT = int(os.getenv("PORT", "5000"))

MAX_QUESTION_CHARS = 2000   # evita prompts gigantes desde la web
MAX_HISTORY_MESSAGES = 12   # últimos mensajes que se envían como contexto
NETWORK_TERMS = (
    "access point",
    "arp",
    "broadcast",
    "cidr",
    "cortafuego",
    "dhcp",
    "dns",
    "ethernet",
    "firewall",
    "gateway",
    "http",
    "https",
    "host de red",
    "icmp",
    "ip",
    "ipconfig",
    "ipv4",
    "ipv6",
    "lan",
    "mac",
    "modem",
    "nat",
    "nslookup",
    "osi",
    "paquete ip",
    "paquetes ip",
    "ping",
    "protocolo de red",
    "router",
    "switch",
    "tcp",
    "tracert",
    "traceroute",
    "udp",
    "wan",
    "wi fi",
    "wifi",
    "enrutamiento",
    "direccionamiento",
    "direccion ip",
    "direccion mac",
    "fibra optica",
    "internet",
    "mascara de red",
    "modelo tcp ip",
    "punto de acceso",
    "redes",
    "red local",
    "red informatica",
    "red inalambrica",
    "seguridad de red",
    "seguridad en redes",
    "subred",
    "topologia",
    "trama",
)
FOLLOW_UP_PATTERN = re.compile(
    r"^(?:y\s+)?(?:por\s+que|como\s+asi|que\s+significa|"
    r"puedes\s+(?:explicar|ampliar|dar\s+un\s+ejemplo)|"
    r"me\s+das\s+un\s+ejemplo|dame\s+un\s+ejemplo|"
    r"explica\s+mas|amplia\s+mas|y\s+eso)[\s?!.]*$"
)
GREETING_PATTERN = re.compile(
    r"^(?:hola(?:\s+redtutor)?|buenas|buenos\s+dias|buenas\s+tardes|"
    r"buenas\s+noches|hey|que\s+tal)[\s!?.]*$"
)
GREETING_REPLY = (
    "¡Hola! Soy RedTutor IA. Puedo ayudarte con fundamentos de redes: "
    "¿qué te gustaría aprender hoy?"
)
OUT_OF_SCOPE_REPLY = (
    "Soy RedTutor IA, un tutor especializado exclusivamente en fundamentos de redes "
    "informáticas. Solo puedo responder consultas relacionadas con redes, como "
    "direccionamiento IP, modelo OSI, routers, switches y protocolos. ¿Qué duda de "
    "redes te gustaría revisar?"
)


def normalize_text(text):
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def is_greeting(text):
    """Reconoce saludos simples, sin permitir que habiliten preguntas ajenas al tema."""
    normalized = normalize_text(text).strip("¿¡ \t\r\n")
    return bool(GREETING_PATTERN.fullmatch(normalized))


def is_network_question(question, history=None):
    """Permite preguntas de redes y seguimientos breves de una pregunta de redes."""
    normalized = normalize_text(question).strip("¿¡ \t\r\n")
    if any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized)
        for term in NETWORK_TERMS
    ):
        return True
    if re.search(r"\bmascara\b.{0,8}/(?:[0-9]|[12][0-9]|3[0-2])\b", normalized):
        return True

    if FOLLOW_UP_PATTERN.fullmatch(normalized.strip()) and history:
        previous_questions = [
            item.get("content", "")
            for item in history
            if item.get("role") == "user" and isinstance(item.get("content"), str)
        ]
        return bool(
            previous_questions and is_network_question(previous_questions[-1])
        )
    return False


def fixed_reply_stream(reply):
    """Devuelve una respuesta fija sin invocar el modelo."""
    events = (
        {"delta": reply},
        {"done": True, "seconds": 0, "eval_count": 0},
    )
    return Response(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        mimetype="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


def load_system_prompt():
    """Lee las instrucciones SYSTEM del Modelfile para aplicarlas en cada consulta web."""
    modelfile = Path(__file__).with_name("Modelfile").read_text(encoding="utf-8")
    match = re.search(r'^SYSTEM\s+"""(.*?)"""', modelfile, re.MULTILINE | re.DOTALL)
    if not match or not match.group(1).strip():
        raise RuntimeError("No se encontró un bloque SYSTEM válido en Modelfile.")
    return match.group(1).strip()


SYSTEM_PROMPT = load_system_prompt()

app = Flask(__name__)


class OllamaError(Exception):
    """Error con un mensaje claro para mostrar al usuario."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.message = message
        self.status = status


# ------------------------------------------------------------------ utilidades
def build_messages(question, history, system_prompt=SYSTEM_PROMPT):
    """Construye los mensajes de Ollama, aplicando el SYSTEM antes del historial."""
    messages = [{"role": "system", "content": system_prompt}]
    for item in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = item.get("role")
        content = str(item.get("content", ""))[:MAX_QUESTION_CHARS * 2]
        if role in ("user", "assistant") and content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})
    return messages


def validate_question(data):
    question = str((data or {}).get("question", "")).strip()
    if not question:
        raise OllamaError("Escribe una pregunta antes de enviar.", 400)
    if len(question) > MAX_QUESTION_CHARS:
        raise OllamaError(
            f"La pregunta es muy larga (máximo {MAX_QUESTION_CHARS} caracteres).", 400
        )
    return question


def explain_http_error(resp, model):
    """Traduce errores HTTP de Ollama a mensajes comprensibles."""
    try:
        detail = resp.json().get("error", resp.text)
    except ValueError:
        detail = resp.text
    if resp.status_code == 404 or "not found" in detail.lower():
        if model == REDTUTOR_MODEL:
            hint = f"Créalo con: ollama create {model} -f Modelfile"
        else:
            hint = f"Descárgalo con: ollama pull {model}"
        return OllamaError(f"El modelo '{model}' no existe en Ollama. {hint}", 404)
    return OllamaError(f"Ollama respondió con error {resp.status_code}: {detail}", 502)


def ollama_post(payload, stream):
    """POST a /api/chat de Ollama con manejo de errores de conexión."""
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            stream=stream,
            timeout=(5, OLLAMA_TIMEOUT),
        )
    except requests.exceptions.ConnectionError:
        raise OllamaError(
            f"No se pudo conectar con Ollama en {OLLAMA_HOST}. "
            "Verifica que Ollama esté abierto (ícono en la barra de tareas) "
            "o ejecuta 'ollama serve'.",
            503,
        )
    except requests.exceptions.Timeout:
        raise OllamaError(
            "Ollama tardó demasiado en responder (timeout). "
            "La primera consulta carga el modelo en memoria; intenta de nuevo.",
            504,
        )
    if resp.status_code != 200:
        raise explain_http_error(resp, payload["model"])
    return resp


def ask_once(model, question, options=None, system_prompt=None):
    """Consulta sin streaming. Devuelve texto y métricas."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if options:
        payload["options"] = options
    start = time.perf_counter()
    resp = ollama_post(payload, stream=False)
    elapsed = time.perf_counter() - start
    data = resp.json()
    content = data.get("message", {}).get("content", "")
    return {
        "model": model,
        "content": content,
        "seconds": round(elapsed, 2),
        "words": len(content.split()),
        "eval_count": data.get("eval_count"),
    }


# ------------------------------------------------------------------ rutas
@app.get("/")
def index():
    return render_template(
        "index.html", redtutor_model=REDTUTOR_MODEL, base_model=BASE_MODEL
    )


@app.get("/api/health")
def health():
    """Indica si Ollama responde y si los modelos están instalados."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        resp.raise_for_status()
        names = [m.get("name", "") for m in resp.json().get("models", [])]
    except requests.exceptions.RequestException:
        return jsonify({"ollama": False, "host": OLLAMA_HOST, "models": {}}), 503

    def installed(model):
        wanted = model if ":" in model else model + ":latest"
        return wanted in names or model in names

    return jsonify(
        {
            "ollama": True,
            "host": OLLAMA_HOST,
            "models": {
                REDTUTOR_MODEL: installed(REDTUTOR_MODEL),
                BASE_MODEL: installed(BASE_MODEL),
            },
        }
    )


@app.post("/api/chat")
def chat():
    """Envía la pregunta a RedTutor y retransmite la respuesta en streaming.

    Formato de salida (NDJSON, una línea JSON por evento):
        {"delta": "texto parcial"}
        {"done": true, "seconds": 3.2, "eval_count": 250}
        {"error": "mensaje"}   (si algo falla a mitad del stream)
    """
    data = request.get_json(silent=True) or {}
    try:
        question = validate_question(data)
        if is_greeting(question):
            return fixed_reply_stream(GREETING_REPLY)
        if not is_network_question(question, data.get("history")):
            return fixed_reply_stream(OUT_OF_SCOPE_REPLY)
        payload = {
            "model": REDTUTOR_MODEL,
            "messages": build_messages(question, data.get("history")),
            "stream": True,
        }
        upstream = ollama_post(payload, stream=True)
    except OllamaError as err:
        return jsonify({"error": err.message}), err.status

    def generate():
        start = time.perf_counter()
        try:
            for line in upstream.iter_lines(decode_unicode=True):
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    yield json.dumps({"error": chunk["error"]}) + "\n"
                    return
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    yield json.dumps({"delta": piece}, ensure_ascii=False) + "\n"
                if chunk.get("done"):
                    yield json.dumps(
                        {
                            "done": True,
                            "seconds": round(time.perf_counter() - start, 2),
                            "eval_count": chunk.get("eval_count"),
                        }
                    ) + "\n"
                    return
        except requests.exceptions.RequestException:
            yield json.dumps(
                {"error": "Se perdió la conexión con Ollama durante la respuesta."}
            ) + "\n"
        finally:
            upstream.close()

    return Response(
        stream_with_context(generate()),
        mimetype="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.post("/api/compare")
def compare():
    """Misma pregunta, sin historial, al modelo base y a RedTutor.

    El modelo base se consulta con su configuración por defecto y RedTutor con
    la del Modelfile: así se observa el efecto combinado de SYSTEM + PARAMETER.
    """
    data = request.get_json(silent=True) or {}
    try:
        question = validate_question(data)
    except OllamaError as err:
        return jsonify({"error": err.message}), err.status

    # Secuencial a propósito: así cada modelo usa toda la RAM/GPU disponible y
    # los tiempos medidos son comparables. En preguntas fuera de redes, se deja
    # responder al modelo base y RedTutor muestra el rechazo del tema.
    results = {}
    for key, model in (("base", BASE_MODEL), ("redtutor", REDTUTOR_MODEL)):
        if key == "redtutor" and not is_network_question(question):
            results[key] = {
                "model": model,
                "content": OUT_OF_SCOPE_REPLY,
                "seconds": 0,
                "words": len(OUT_OF_SCOPE_REPLY.split()),
            }
            continue
        try:
            prompt = SYSTEM_PROMPT if key == "redtutor" else None
            results[key] = ask_once(model, question, system_prompt=prompt)
        except OllamaError as err:
            results[key] = {"error": err.message}
        except Exception as err:  # noqa: BLE001 - se informa al usuario
            results[key] = {"error": f"Error inesperado: {err}"}

    status = 200 if any("content" in r for r in results.values()) else 502
    return jsonify({"question": question, **results}), status


if __name__ == "__main__":
    print(f" * RedTutor IA -> http://localhost:{PORT}")
    print(f" * Ollama: {OLLAMA_HOST} | modelo: {REDTUTOR_MODEL} | base: {BASE_MODEL}")
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
