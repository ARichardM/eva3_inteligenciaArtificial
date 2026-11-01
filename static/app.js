/* RedTutor IA - lógica de la interfaz (sin frameworks ni CDNs) */
(() => {
  "use strict";

  const chat = document.getElementById("chat");
  const form = document.getElementById("composer");
  const input = document.getElementById("question");
  const sendBtn = document.getElementById("sendBtn");
  const clearBtn = document.getElementById("clearBtn");
  const compareMode = document.getElementById("compareMode");
  const statusEl = document.getElementById("status");
  const welcomeHTML = document.getElementById("welcome").outerHTML;
  const CFG = window.REDTUTOR || { model: "redtutor", base: "llama3.2:3b" };

  /** Historial de la sesión (se pierde al recargar: no hay base de datos). */
  let history = [];
  let busy = false;

  // ------------------------------------------------------------ Markdown básico
  const escapeHTML = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function inline(text) {
    // `text` ya viene escapado
    return text
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  }

  function renderTable(rows) {
    const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
    const head = cells(rows[0]);
    const body = rows.slice(2).map(cells);
    return "<table><thead><tr>" + head.map((c) => `<th>${c}</th>`).join("") +
      "</tr></thead><tbody>" +
      body.map((r) => "<tr>" + r.map((c) => `<td>${c}</td>`).join("") + "</tr>").join("") +
      "</tbody></table>";
  }

  /** Convierte un subconjunto de Markdown a HTML seguro (todo se escapa primero). */
  function renderMarkdown(src) {
    const lines = escapeHTML(src).split("\n");
    let html = "", i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (/^```/.test(line.trim())) {                       // bloque de código
        const buf = []; i++;
        while (i < lines.length && !/^```/.test(lines[i].trim())) buf.push(lines[i++]);
        i++;
        html += `<pre><code>${buf.join("\n")}</code></pre>`;
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        const buf = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) buf.push(lines[i++]);
        html += renderTable(buf);
        continue;
      }
      const h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) { html += `<h${h[1].length > 2 ? 4 : 3}>${inline(h[2])}</h${h[1].length > 2 ? 4 : 3}>`; i++; continue; }
      if (/^\s*([-*•])\s+/.test(line)) {
        html += "<ul>";
        while (i < lines.length && /^\s*([-*•])\s+/.test(lines[i]))
          html += `<li>${inline(lines[i++].replace(/^\s*[-*•]\s+/, ""))}</li>`;
        html += "</ul>";
        continue;
      }
      if (/^\s*\d+[.)]\s+/.test(line)) {
        const start = parseInt(line, 10) || 1;
        html += `<ol start="${start}">`;
        while (i < lines.length && /^\s*\d+[.)]\s+/.test(lines[i]))
          html += `<li>${inline(lines[i++].replace(/^\s*\d+[.)]\s+/, ""))}</li>`;
        html += "</ol>";
        continue;
      }
      if (!line.trim()) { i++; continue; }
      const para = [];
      while (i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|\s*[-*•]\s|\s*\d+[.)]\s|\s*\|)/.test(lines[i]))
        para.push(lines[i++]);
      if (!para.length) para.push(lines[i++]);
      html += `<p>${inline(para.join("<br>"))}</p>`;
    }
    return html;
  }

  // ------------------------------------------------------------ elementos DOM
  function removeWelcome() {
    const w = document.getElementById("welcome");
    if (w) w.remove();
  }

  function addMessage(role, text) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = role === "user" ? "Tú" : "RedTutor IA";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "user") bubble.textContent = text;
    else bubble.innerHTML = text ? renderMarkdown(text) : "";
    wrap.append(who, bubble);
    chat.appendChild(wrap);
    scrollDown();
    return { wrap, bubble };
  }

  const thinkingHTML = (label = "RedTutor está pensando") =>
    `<span class="thinking">${label}<span class="dots"><span></span><span></span><span></span></span></span>`;

  function addMeta(wrap, text) {
    const m = document.createElement("span");
    m.className = "meta";
    m.textContent = text;
    wrap.appendChild(m);
  }

  const scrollDown = () => window.scrollTo({ top: document.body.scrollHeight });

  function setBusy(state) {
    busy = state;
    sendBtn.disabled = state;
    input.disabled = state;
    document.querySelectorAll(".chip").forEach((c) => (c.disabled = state));
    if (!state) input.focus();
  }

  async function readError(resp) {
    try { return (await resp.json()).error || `Error HTTP ${resp.status}`; }
    catch { return `Error HTTP ${resp.status}`; }
  }

  // ------------------------------------------------------------ chat (streaming)
  async function sendChat(question) {
    addMessage("user", question);
    const { wrap, bubble } = addMessage("bot", "");
    bubble.innerHTML = thinkingHTML();
    let answer = "";
    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history }),
      });
      if (!resp.ok) throw new Error(await readError(resp));

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "", meta = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          const evt = JSON.parse(line);
          if (evt.error) throw new Error(evt.error);
          if (evt.delta) { answer += evt.delta; bubble.innerHTML = renderMarkdown(answer); scrollDown(); }
          if (evt.done) meta = evt;
        }
      }
      if (!answer.trim()) throw new Error("El modelo no devolvió texto.");
      history.push({ role: "user", content: question }, { role: "assistant", content: answer });
      if (meta) addMeta(wrap, `${meta.seconds} s · ${answer.split(/\s+/).length} palabras`);
    } catch (err) {
      wrap.classList.add("error");
      bubble.textContent = "Error: " + (err.message || "Error desconocido");
    }
  }

  // ------------------------------------------------------------ modo comparar
  async function sendCompare(question) {
    addMessage("user", question);
    const wrap = document.createElement("div");
    wrap.className = "msg bot";
    wrap.innerHTML = `<span class="who">Comparación</span>
      <div class="compare">
        <div class="col base"><span class="tag">Modelo base · ${escapeHTML(CFG.base)}</span><div class="bubble">${thinkingHTML("Generando")}</div></div>
        <div class="col tutor"><span class="tag">RedTutor IA · ${escapeHTML(CFG.model)}</span><div class="bubble">${thinkingHTML("En espera")}</div></div>
      </div>`;
    chat.appendChild(wrap);
    scrollDown();
    const fill = (col, r) => {
      const box = wrap.querySelector(`.col.${col} .bubble`);
      if (!r || r.error) {
        box.parentElement.parentElement.parentElement.classList.add("error");
        box.textContent = "Error: " + ((r && r.error) || "Sin respuesta");
        return;
      }
      box.innerHTML = renderMarkdown(r.content);
      const m = document.createElement("span");
      m.className = "meta";
      m.textContent = `${r.seconds} s · ${r.words} palabras`;
      box.after(m);
    };
    try {
      const resp = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await resp.json().catch(() => ({}));
      if (data.error && !data.base) throw new Error(data.error);
      fill("base", data.base);
      fill("tutor", data.redtutor);
    } catch (err) {
      fill("base", { error: err.message });
      fill("tutor", { error: err.message });
    }
    scrollDown();
  }

  // ------------------------------------------------------------ eventos
  async function submit(question) {
    question = (question || "").trim();
    if (!question || busy) return;
    removeWelcome();
    input.value = "";
    autoGrow();
    setBusy(true);
    try {
      if (compareMode.checked) await sendCompare(question);
      else await sendChat(question);
    } finally {
      setBusy(false);
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); submit(input.value); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(input.value); }
  });
  const autoGrow = () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 180) + "px"; };
  input.addEventListener("input", autoGrow);

  chat.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip) submit(chip.textContent);
  });

  clearBtn.addEventListener("click", () => {
    if (busy) return;
    history = [];
    chat.innerHTML = welcomeHTML;
    input.focus();
  });

  // ------------------------------------------------------------ estado de Ollama
  async function checkHealth() {
    try {
      const r = await fetch("/api/health");
      const d = await r.json();
      if (!d.ollama) { statusEl.className = "status err"; statusEl.textContent = "Ollama apagado"; return; }
      const missing = Object.entries(d.models).filter(([, ok]) => !ok).map(([m]) => m);
      if (missing.length) {
        statusEl.className = "status warn";
        statusEl.textContent = "Falta: " + missing.join(", ");
      } else {
        statusEl.className = "status ok";
        statusEl.textContent = "Ollama conectado";
      }
    } catch {
      statusEl.className = "status err";
      statusEl.textContent = "Servidor sin respuesta";
    }
  }
  checkHealth();
  setInterval(checkHealth, 30000);
  input.focus();
})();
