# Guion del video — RedTutor IA (Evaluación 3, Opción A)

**Duración objetivo:** 11:00 (margen de 1 minuto bajo el límite de 12)
**Formato:** grabación de pantalla + cámara pequeña (OBS Studio o la grabadora de Xbox Game Bar `Win + G`). Subir a YouTube como "No listado" y pegar el enlace en la entrega.

## Preparación antes de grabar

- [ ] Ollama abierto; `ollama list` muestra `redtutor:latest` y `llama3.2:3b`.
- [ ] Hacer **una consulta previa** a cada modelo para que ya estén cargados en memoria (evita esperas largas en vivo).
- [ ] `python app.py` corriendo y http://localhost:5000 abierto y limpio.
- [ ] `pruebas/experimentos.py` ya ejecutado; `pruebas/resultados/resumen.md` abierto en VS Code.
- [ ] PowerShell en la carpeta del proyecto, fuente grande (Ctrl + rueda) para que se lea.
- [ ] Notificaciones desactivadas (Asistente de concentración).
- [ ] Informe en Word abierto en la sección de experimentación, por si se quiere mostrar una tabla.

## Reparto y tiempos

| Bloque | Parte del enunciado | Responsable | Tiempo | Acumulado |
|---|---|---|---|---|
| 0 | Presentación de los integrantes | Los tres | 0:30 | 0:30 |
| 1 | Parte 1: Presentación del proyecto | Patricio Arias | 1:00 | 1:30 |
| 2 | Parte 2: Explicación del modelo (Modelfile) | Sebastián Urrutia | 2:00 | 3:30 |
| 3 | Parte 3: Configuración y parámetros | Agustín Richard | 2:00 | 5:30 |
| 4 | Parte 4: Evidencia de funcionamiento (terminal + web) | Sebastián Urrutia | 2:00 | 7:30 |
| 5 | Parte 5: Comparación (3 consultas) | Patricio Arias | 2:15 | 9:45 |
| 6 | Parte 6: Preguntas de cierre | Agustín Richard (1, 2) y Patricio Arias (3, 4) | 1:00 | 10:45 |
| 7 | Cierre | Sebastián Urrutia | 0:15 | 11:00 |

Cada integrante expone al menos dos bloques, lo que permite demostrar dominio conceptual (criterio 7).

---

## Bloque 0 — Presentación de los integrantes (0:00 – 0:30)

**En pantalla:** portada del informe o la web de RedTutor IA en la pantalla de bienvenida. Cámaras de los tres.

- **Patricio:** "Hola, soy Patricio Arias, estudiante de Ingeniería en Informática de INACAP."
- **Sebastián:** "Soy Sebastián Urrutia, también de Ingeniería en Informática."
- **Agustín:** "Y yo soy Agustín Richard. Les presentamos nuestro proyecto de la Evaluación 3 de Aplicaciones de Inteligencia Artificial: RedTutor IA."

## Bloque 1 — Parte 1: Presentación del proyecto · Patricio (0:30 – 1:30)

**En pantalla:** la web con la pantalla de bienvenida y las tres preguntas sugeridas.

> "El tema que elegimos es **Redes**, específicamente fundamentos de redes informáticas: modelos OSI y TCP/IP, direccionamiento IPv4, dispositivos como routers y switches, protocolos como TCP, UDP, DHCP, DNS e ICMP, y diagnóstico con ping, ipconfig y tracert.
>
> El **objetivo** de RedTutor IA es ser un tutor que apoye a estudiantes de nivel inicial e intermedio, respondiendo con una estructura pedagógica fija: definición, ejemplo, pasos o comandos cuando corresponde, y un resumen. Todo corre **localmente** con Ollama, sin depender de servicios en la nube, lo que lo hace viable para un laboratorio de la institución.
>
> Queremos demostrar que, partiendo del mismo modelo base, la personalización con un Modelfile produce respuestas más especializadas y útiles que el modelo original."

## Bloque 2 — Parte 2: Explicación del modelo · Sebastián (1:30 – 3:30)

**En pantalla:** `Modelfile` abierto en VS Code. Ir bajando por secciones mientras se explica.

> "El **modelo base** es `llama3.2:3b` de Meta, de 3 mil millones de parámetros. Lo elegimos porque ocupa cerca de 2 GB, corre en un notebook sin GPU dedicada y entiende español."

*(Señalar la línea `FROM llama3.2:3b`.)*

> "El **rol** está definido en el SYSTEM: 'Eres RedTutor IA, un tutor virtual de fundamentos de redes informáticas para estudiantes en Chile'. Las **principales instrucciones** son: responder siempre en español; limitarse a seis áreas temáticas; seguir el formato definición, ejemplo, pasos y resumen; usar tablas en comparaciones; pedir aclaración si la pregunta es ambigua; reconocer cuando no sabe algo y no inventar comandos ni RFC; y redirigir cortésmente las preguntas que no son de redes."

*(Bajar a la sección "Conocimiento de referencia".)*

> "Para **usar el documento de referencia**, que es el libro abierto *Computer Networking: Principles, Protocols and Practice* de Olivier Bonaventure, complementado con los RFC 1918, 791 y 792, condensamos los datos clave dentro del SYSTEM: las 7 capas OSI y las 4 de TCP/IP, las PDU de cada capa, la fórmula de hosts 2 elevado a 32 menos el prefijo, menos 2, el ejemplo del /24 con 254 hosts, los tres rangos privados del RFC 1918, el significado de 169.254 y un orden de diagnóstico de abajo hacia arriba. Así el modelo tiene una 'hoja de referencia' que no debe contradecir. Es importante aclarar que esto no es RAG: el modelo no lee el PDF en tiempo real, sino que las reglas extraídas quedan fijas en el SYSTEM."

## Bloque 3 — Parte 3: Configuración y parámetros · Agustín (3:30 – 5:30)

**En pantalla:** primero las líneas `PARAMETER` del Modelfile; luego `pruebas/resultados/resumen.md` (o la tabla del informe), y si alcanza, `temperatura.md` mostrando dos respuestas.

> "Los **parámetros modificados** fueron temperature, top_p, repeat_penalty, num_ctx y num_predict. Para medir su efecto creamos el script `experimentos.py`, que manda la misma pregunta del /24 cambiando un parámetro a la vez y guarda tiempo, cantidad de palabras, si respeta el formato y si da el dato correcto de 254 hosts."

*(Mostrar la tabla de temperatura.)*

> "Con **temperature** probamos 0.1, 0.3, 0.7 y 1.0. [COMPLETAR con lo observado, por ejemplo: con 0.1 las respuestas fueron casi idénticas pero algo rígidas; con 1.0 el modelo divagó / cambió el formato / cometió X error]."
>
> "Con **top_p** comparamos 0.5 y 0.9: [COMPLETAR: con 0.5 el vocabulario fue más repetitivo…]."
>
> "Con **repeat_penalty** probamos 1.0, 1.1 y 1.3: [COMPLETAR: con 1.3 el modelo evitaba repetir términos como 'máscara' o 'red' y usaba sinónimos forzados…]."
>
> "La **configuración final** es temperature 0.3, top_p 0.9, top_k 40, repeat_penalty 1.1, num_ctx 4096 y num_predict 700. La **justificación técnica**: en un tutor técnico importa más la exactitud y la consistencia que la creatividad, por eso una temperatura baja; top_p 0.9 conserva un lenguaje natural; 1.1 de penalización evita repeticiones sin castigar términos técnicos que sí deben repetirse; 4096 de contexto alcanza para el SYSTEM más varias preguntas de la conversación; y 700 tokens limita respuestas eternas."

## Bloque 4 — Parte 4: Evidencia de funcionamiento · Sebastián (5:30 – 7:30)

**En pantalla:** PowerShell en la carpeta del proyecto. Ejecutar en vivo:

```powershell
ollama create redtutor -f Modelfile
```
> "Primero demostramos que el modelo **fue creado correctamente**: `ollama create` lee el Modelfile y termina en *success*."

```powershell
ollama list
```
> "Con `ollama list` vemos que `redtutor:latest` **está disponible para su uso** junto al modelo base."

```powershell
ollama show redtutor --modelfile
```
*(Bajar rápido hasta los PARAMETER.)* > "Y aquí Ollama confirma los parámetros aplicados."

```powershell
ollama run redtutor "¿Qué comando uso para ver mi dirección IP en Windows?"
```
> "Ahora **responde desde la terminal**: vemos la definición, el comando `ipconfig` en bloque de código y el resumen."

**Cambiar al navegador** (Flask ya corriendo; mostrar un segundo la terminal con `python app.py`).

> "Y ahora la **interfaz web**. Flask sirve la página y hace de intermediario con la API local de Ollama en el puerto 11434. Arriba se ve el indicador 'Ollama conectado'."

*(Escribir: "¿Qué es DHCP y qué significa una IP 169.254?" y enviar.)*

> "La respuesta llega en streaming, con el indicador 'pensando', Markdown renderizado y el tiempo de respuesta. Como mejoras de usabilidad agregamos preguntas sugeridas, historial de la sesión, botón limpiar, manejo de errores y el modo comparar, que veremos ahora."

## Bloque 5 — Parte 5: Comparación · Patricio (7:30 – 9:45)

**En pantalla:** web, pulsar **Limpiar** y activar **"Comparar con modelo base"**. Ir pulsando las 3 preguntas sugeridas (si demoran, cortar la espera en la edición).

1. **P1: "¿Cuál es la diferencia entre un router y un switch?"**
   > "A la izquierda el modelo base, a la derecha RedTutor. [COMPLETAR según lo que se vea: el base responde en párrafos generales / en inglés / sin ejemplo; RedTutor entrega definición, ejemplo de una oficina, una tabla capa 2 vs capa 3 y un resumen]."
2. **P2: "¿Qué significa una dirección IPv4 con máscara /24?"**
   > "Aquí lo clave es la precisión: RedTutor muestra 255.255.255.0, 256 direcciones, 254 hosts y el ejemplo 192.168.1.0 con broadcast .255. [COMPLETAR: qué hizo el base]."
3. **P3: "¿Qué pasos debo seguir si un computador no tiene conexión a la red?"**
   > "RedTutor sigue un orden de diagnóstico de abajo hacia arriba, con los comandos `ipconfig /all`, `ping 127.0.0.1`, ping al gateway, a 8.8.8.8 y a un dominio para aislar DNS. [COMPLETAR: comparación con el base]."

**Extra (si hay tiempo, 20 s):** desactivar comparar y preguntar "¿Me das una receta de queque?" → RedTutor redirige a redes.

> "En nuestra evaluación con la escala de 1 a 5 en precisión, claridad, especialización y utilidad práctica, el modelo base obtuvo [COMPLETAR] de 60 puntos y RedTutor [COMPLETAR] de 60. La diferencia es apreciable sobre todo en especialización y utilidad práctica."

## Bloque 6 — Parte 6: Preguntas de cierre (9:45 – 10:45)

**En pantalla:** diapositiva o sección "Respuestas a la Parte 6" del informe.

- **Agustín — 1. Principal dificultad:** "Lograr que un modelo pequeño de 3B respetara el formato y no inventara datos. Tuvimos que escribir el SYSTEM de forma muy concreta, con datos de referencia explícitos, y probar varias versiones. [COMPLETAR/ajustar con la experiencia real, por ejemplo tiempos de respuesta en CPU]."
- **Agustín — 2. Parámetro de mayor impacto:** "La **temperature**: [COMPLETAR con lo observado, por ejemplo: al subirla a 1.0 cambió el formato y aparecieron errores en el cálculo de hosts], por eso la dejamos en 0.3."
- **Patricio — 3. Mejora futura:** "Incorporar **RAG** para que el modelo consulte directamente el libro y los apuntes del curso, citar la fuente de cada respuesta, guardar historial por estudiante y agregar ejercicios de subnetting autoevaluados."
- **Patricio — 4. Aplicaciones reales:** "Un tutor 24/7 en laboratorios de redes de INACAP, apoyo para preparar certificaciones como CCNA, asistente de primer nivel para mesas de ayuda que guía el diagnóstico básico, y como corre local, se puede usar en salas sin internet y sin enviar datos de estudiantes a terceros."

## Bloque 7 — Cierre · Sebastián (10:45 – 11:00)

> "En resumen, con un Modelfile bien diseñado transformamos un modelo general de 3B en un tutor de redes especializado, local y conectado a una web. Gracias por su atención."

---

## Checklist final contra la rúbrica (revisar antes de subir)

| Criterio (pts) | Qué debe verse en el video | ✔ |
|---|---|---|
| 1. Entorno IA local (15) | `ollama list`, `ollama run`, diagrama/explicación Navegador → Flask → Ollama → modelo | ☐ |
| 2. Diseño (20) | Modelfile en pantalla: FROM, SYSTEM (rol, alcance, formato, reglas, conocimiento de referencia), PARAMETER y **por qué** cada decisión | ☐ |
| 3. Parámetros (15) | Valores probados de temperature, top_p y repeat_penalty, efecto observado de cada uno, configuración final justificada | ☐ |
| 4. Interfaz (15) | Web conectada a `redtutor`, streaming, preguntas sugeridas, limpiar, indicador de estado, **modo comparar** | ☐ |
| 5. Función (15) | 3 consultas respondidas con el formato definido + pregunta fuera de tema redirigida | ☐ |
| 6. Evidencias (10) | `ollama create` (success), `ollama list`, terminal, web; capturas en el informe | ☐ |
| 7. Comunicación (10) | Los tres se presentan primero y todos explican con propiedad; responden Parte 6 | ☐ |
| Enunciado | Duración < 12 min, enlace de YouTube funcionando (No listado, no Privado) | ☐ |

**Antes de subir:** reemplazar todos los `[COMPLETAR]` de este guion por lo observado realmente en `pruebas/resultados/`.
