"""
RedTutor IA - Experimentos de parámetros y comparación base vs personalizado
============================================================================

Uso (desde la carpeta del proyecto, con Ollama abierto y el modelo creado):

    python pruebas/experimentos.py              # todo (comparación + parámetros)
    python pruebas/experimentos.py --solo comparacion
    python pruebas/experimentos.py --solo parametros
    python pruebas/experimentos.py --dry-run    # muestra el plan sin llamar a Ollama
    python pruebas/experimentos.py --repeticiones 2   # repite cada prueba (consistencia)

Genera en pruebas/resultados/:
    comparacion.md / comparacion.csv   -> 3 preguntas, modelo base vs redtutor
    temperatura.md                     -> barrido de temperature (0.1, 0.3, 0.7, 1.0)
    top_p.md                           -> barrido de top_p (0.5, 0.9)
    repeat_penalty.md                  -> barrido de repeat_penalty (1.0, 1.1, 1.3)
    parametros.csv                     -> todas las corridas de parámetros
    resumen.md                         -> tablas resumen para pegar en el informe
    rubrica_puntajes.csv               -> plantilla para puntuar 1-5 (llenar a mano)

Solo usa la biblioteca estándar de Python (no requiere instalar nada extra).
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_HOST.startswith("http"):
    OLLAMA_HOST = "http://" + OLLAMA_HOST
REDTUTOR_MODEL = os.getenv("REDTUTOR_MODEL", "redtutor")
BASE_MODEL = os.getenv("BASE_MODEL", "llama3.2:3b")
OUT_DIR = Path(__file__).resolve().parent / "resultados"

PREGUNTAS = [
    "¿Cuál es la diferencia entre un router y un switch?",
    "¿Qué significa una dirección IPv4 con máscara /24?",
    "¿Qué pasos debo seguir si un computador no tiene conexión a la red?",
]
# Pregunta usada en el barrido de parámetros (pide cálculo + explicación,
# así se nota si el modelo se equivoca o divaga al subir la temperatura).
PREGUNTA_PARAMETROS = PREGUNTAS[1]

# Configuración final del Modelfile: punto de partida de cada barrido.
CONFIG_FINAL = {"temperature": 0.3, "top_p": 0.9, "repeat_penalty": 1.1}
# En la comparación ambos modelos usan los mismos parámetros de generación,
# así la diferencia observada se debe al SYSTEM del Modelfile.
OPCIONES_COMPARACION = {**CONFIG_FINAL, "top_k": 40, "num_ctx": 4096, "num_predict": 700}

BARRIDOS = {
    "temperatura": ("temperature", [0.1, 0.3, 0.7, 1.0]),
    "top_p": ("top_p", [0.5, 0.9]),
    "repeat_penalty": ("repeat_penalty", [1.0, 1.1, 1.3]),
}

# Indicadores automáticos y objetivos (no reemplazan la evaluación humana 1-5).
SECCIONES = ("definición", "ejemplo", "resumen")


def indicadores(texto):
    t = texto.lower()
    palabras = texto.split()
    unicas = len(set(w.lower().strip(".,;:()*`") for w in palabras))
    return {
        "palabras": len(palabras),
        "secciones_formato": sum(1 for s in SECCIONES if s in t),
        "tiene_codigo": "```" in texto or "`ping" in t or "`ipconfig" in t,
        "tiene_tabla": "|---" in texto.replace(" ", "") or "| ---" in texto,
        "menciona_254": "254" in texto,
        "diversidad_lexica": round(unicas / len(palabras), 3) if palabras else 0,
        "en_espanol": sum(t.count(w) for w in (" el ", " la ", " de ", " que "))
        > sum(t.count(w) for w in (" the ", " and ", " is ", " of ")),
    }


def consultar(modelo, pregunta, options=None, timeout=300):
    """Llama a /api/chat de Ollama (sin streaming) y mide el tiempo."""
    payload = {
        "model": modelo,
        "messages": [{"role": "user", "content": pregunta}],
        "stream": False,
    }
    if options:
        payload["options"] = options
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        cuerpo = err.read().decode("utf-8", "replace")
        raise SystemExit(
            f"\n[ERROR] Ollama respondió {err.code} para el modelo '{modelo}': {cuerpo}\n"
            f"        ¿Creaste el modelo? -> ollama create {REDTUTOR_MODEL} -f Modelfile\n"
            f"        ¿Descargaste el base? -> ollama pull {BASE_MODEL}"
        )
    except urllib.error.URLError as err:
        raise SystemExit(
            f"\n[ERROR] No se pudo conectar con Ollama en {OLLAMA_HOST} ({err.reason}).\n"
            "        Abre Ollama o ejecuta 'ollama serve' y vuelve a intentar."
        )
    segundos = time.perf_counter() - inicio
    texto = data.get("message", {}).get("content", "")
    eval_count = data.get("eval_count") or 0
    eval_ns = data.get("eval_duration") or 0
    return {
        "texto": texto,
        "segundos": round(segundos, 2),
        "tokens": eval_count,
        "tokens_por_seg": round(eval_count / (eval_ns / 1e9), 1) if eval_ns else "",
    }


def verificar_ollama():
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as resp:
            nombres = [m["name"] for m in json.loads(resp.read())["models"]]
    except Exception as err:  # noqa: BLE001
        raise SystemExit(f"[ERROR] Ollama no responde en {OLLAMA_HOST}: {err}")
    faltan = [
        m for m in (REDTUTOR_MODEL, BASE_MODEL)
        if m not in nombres and f"{m}:latest" not in nombres
    ]
    if faltan:
        raise SystemExit(f"[ERROR] Faltan modelos en Ollama: {', '.join(faltan)}")
    print(f"Ollama OK en {OLLAMA_HOST}. Modelos: {REDTUTOR_MODEL}, {BASE_MODEL}")


def calentar(modelo):
    """Primera llamada para cargar el modelo en memoria (no se mide)."""
    print(f"  Cargando {modelo} en memoria...", flush=True)
    consultar(modelo, "Hola", options={"num_predict": 5})


def bloque_md(titulo, fila, texto):
    meta = " | ".join(f"{k}: {v}" for k, v in fila.items() if k not in ("respuesta",))
    return f"### {titulo}\n\n_{meta}_\n\n{texto.strip()}\n\n---\n\n"


# ---------------------------------------------------------------- experimentos
def experimento_comparacion(reps):
    print("\n== Comparación modelo base vs RedTutor ==")
    filas, md = [], [
        "# Comparación modelo base vs RedTutor IA\n\n",
        f"Fecha: {datetime.now():%d/%m/%Y %H:%M} · Host: {OLLAMA_HOST}\n\n",
        "Ambos modelos se consultan con los mismos parámetros de generación "
        f"({OPCIONES_COMPARACION}); la única diferencia es el SYSTEM del Modelfile "
        "de RedTutor. Así la comparación aísla el efecto de la especialización.\n\n",
    ]
    for modelo in (BASE_MODEL, REDTUTOR_MODEL):
        calentar(modelo)
        for n, pregunta in enumerate(PREGUNTAS, 1):
            for rep in range(1, reps + 1):
                print(f"  [{modelo}] P{n} rep {rep}...", flush=True)
                r = consultar(modelo, pregunta, options=OPCIONES_COMPARACION)
                fila = {
                    "modelo": modelo, "pregunta_n": n, "repeticion": rep,
                    "pregunta": pregunta, "segundos": r["segundos"],
                    "tokens": r["tokens"], "tokens_por_seg": r["tokens_por_seg"],
                    **indicadores(r["texto"]), "respuesta": r["texto"],
                }
                filas.append(fila)
                md.append(bloque_md(f"P{n} · {modelo} · rep {rep}: {pregunta}", fila, r["texto"]))
    guardar("comparacion", filas, md)
    return filas


def experimento_parametros(reps):
    print("\n== Barrido de parámetros sobre RedTutor ==")
    calentar(REDTUTOR_MODEL)
    todas = []
    for nombre, (param, valores) in BARRIDOS.items():
        md = [
            f"# Barrido de {param}\n\n",
            f"Modelo: {REDTUTOR_MODEL} · Pregunta: \"{PREGUNTA_PARAMETROS}\"\n\n",
            f"Resto de parámetros fijos en la configuración final: {CONFIG_FINAL}\n\n",
        ]
        filas = []
        for valor in valores:
            opciones = {**CONFIG_FINAL, param: valor}
            for rep in range(1, reps + 1):
                print(f"  {param}={valor} rep {rep}...", flush=True)
                r = consultar(REDTUTOR_MODEL, PREGUNTA_PARAMETROS, options=opciones)
                fila = {
                    "experimento": nombre, "parametro": param, "valor": valor,
                    "repeticion": rep, "segundos": r["segundos"], "tokens": r["tokens"],
                    "tokens_por_seg": r["tokens_por_seg"], **indicadores(r["texto"]),
                    "respuesta": r["texto"],
                }
                filas.append(fila)
                md.append(bloque_md(f"{param} = {valor} · rep {rep}", fila, r["texto"]))
        md.append(
            "## Observaciones del grupo\n\n"
            "[COMPLETAR: describir cómo cambió la respuesta con cada valor]\n"
        )
        escribir(OUT_DIR / f"{nombre}.md", "".join(md))
        todas.extend(filas)
    escribir_csv(OUT_DIR / "parametros.csv", todas)
    return todas


# ---------------------------------------------------------------- salida
def escribir(ruta, texto):
    ruta.write_text(texto, encoding="utf-8")
    print(f"  -> {ruta.relative_to(OUT_DIR.parent.parent)}")


def escribir_csv(ruta, filas):
    if not filas:
        return
    with ruta.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: Excel lo abre bien
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(filas)
    print(f"  -> {ruta.relative_to(OUT_DIR.parent.parent)}")


def guardar(nombre, filas, md):
    escribir(OUT_DIR / f"{nombre}.md", "".join(md))
    escribir_csv(OUT_DIR / f"{nombre}.csv", filas)


def promedio(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else ""


def resumen(comp, params):
    md = ["# Resumen de resultados (para pegar en el informe)\n\n"]
    if comp:
        md.append("## Comparación base vs RedTutor (promedios por pregunta)\n\n")
        md.append("| Pregunta | Modelo | Segundos | Palabras | Secciones formato (0-3) | Código | Tabla | Español |\n")
        md.append("|---|---|---|---|---|---|---|---|\n")
        for n in range(1, len(PREGUNTAS) + 1):
            for modelo in (BASE_MODEL, REDTUTOR_MODEL):
                g = [f for f in comp if f["pregunta_n"] == n and f["modelo"] == modelo]
                md.append(
                    f"| P{n} | {modelo} | {promedio([f['segundos'] for f in g])} | "
                    f"{promedio([f['palabras'] for f in g])} | "
                    f"{promedio([f['secciones_formato'] for f in g])} | "
                    f"{'sí' if any(f['tiene_codigo'] for f in g) else 'no'} | "
                    f"{'sí' if any(f['tiene_tabla'] for f in g) else 'no'} | "
                    f"{'sí' if all(f['en_espanol'] for f in g) else 'no'} |\n"
                )
        md.append("\n")
    if params:
        md.append("## Barrido de parámetros (promedios)\n\n")
        md.append("| Parámetro | Valor | Segundos | Palabras | Diversidad léxica | Menciona 254 hosts | Secciones formato |\n")
        md.append("|---|---|---|---|---|---|---|\n")
        for _, (param, valores) in BARRIDOS.items():
            for v in valores:
                g = [f for f in params if f["parametro"] == param and f["valor"] == v]
                md.append(
                    f"| {param} | {v} | {promedio([f['segundos'] for f in g])} | "
                    f"{promedio([f['palabras'] for f in g])} | "
                    f"{promedio([f['diversidad_lexica'] for f in g])} | "
                    f"{sum(1 for f in g if f['menciona_254'])}/{len(g)} | "
                    f"{promedio([f['secciones_formato'] for f in g])} |\n"
                )
    escribir(OUT_DIR / "resumen.md", "".join(md))

    # Plantilla de puntuación humana (escala 1-5 del informe, máx. 20)
    plantilla = [
        {"pregunta": f"P{n}", "modelo": m, "precision": "", "claridad": "",
         "especializacion": "", "utilidad_practica": "", "total_20": "", "observacion": ""}
        for n in range(1, len(PREGUNTAS) + 1) for m in (BASE_MODEL, REDTUTOR_MODEL)
    ]
    escribir_csv(OUT_DIR / "rubrica_puntajes.csv", plantilla)


def main():
    ap = argparse.ArgumentParser(description="Experimentos de RedTutor IA con Ollama.")
    ap.add_argument("--solo", choices=["comparacion", "parametros"], help="ejecuta solo una parte")
    ap.add_argument("--repeticiones", type=int, default=1, help="repeticiones por prueba (por defecto 1)")
    ap.add_argument("--dry-run", action="store_true", help="muestra el plan sin llamar a Ollama")
    args = ap.parse_args()

    n_comp = len(PREGUNTAS) * 2 * args.repeticiones
    n_par = sum(len(v) for _, v in BARRIDOS.values()) * args.repeticiones
    print("Plan de experimentos RedTutor IA")
    print(f"  Host Ollama: {OLLAMA_HOST} | RedTutor: {REDTUTOR_MODEL} | Base: {BASE_MODEL}")
    if args.solo != "parametros":
        print(f"  Comparación: {len(PREGUNTAS)} preguntas x 2 modelos x {args.repeticiones} rep = {n_comp} consultas")
    if args.solo != "comparacion":
        for nombre, (p, vals) in BARRIDOS.items():
            print(f"  Barrido {p}: {vals}")
        print(f"  Parámetros: {n_par} consultas sobre \"{PREGUNTA_PARAMETROS}\"")
    print(f"  Salida: {OUT_DIR}")
    if args.dry_run:
        print("\n(dry-run) No se llamó a Ollama.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    verificar_ollama()
    inicio = time.perf_counter()
    comp = experimento_comparacion(args.repeticiones) if args.solo != "parametros" else []
    params = experimento_parametros(args.repeticiones) if args.solo != "comparacion" else []
    resumen(comp, params)
    print(f"\nListo en {time.perf_counter() - inicio:.0f} s. Revisa {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
