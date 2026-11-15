const $ = (id) => document.getElementById(id);
const log = $("log"), input = $("input"), send = $("send");
let history = [];
let busy = false;

function addMsg(cls, text = "") {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function renderSources(el, sources) {
  if (!sources.length) return;
  const s = document.createElement("div");
  s.className = "sources";
  s.append("Sources: ");
  sources.forEach((src, i) => {
    if (i) s.append("  ");
    const label = `[${src.id}] ${src.title}`;
    if (/^https?:\/\//.test(src.url)) {
      const a = document.createElement("a");
      a.href = src.url; a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = label;
      s.append(a);
    } else s.append(label);
  });
  el.appendChild(s);
}

async function loadModels() {
  const r = await fetch("api/models");
  const m = await r.json();
  const sel = $("model"), eff = $("effort");
  m.models.forEach((x) => sel.add(new Option(x.id, x.id)));
  sel.value = localStorage.getItem("burn.model") || m.default;
  if (![...sel.options].some((o) => o.value === sel.value)) sel.value = m.default;
  m.efforts.forEach((e) => eff.add(new Option(e, e)));
  const defaults = Object.fromEntries(m.models.map((x) => [x.id, x.default_effort]));
  const sync = () => { eff.value = defaults[sel.value]; localStorage.setItem("burn.model", sel.value); };
  sel.addEventListener("change", sync);
  sync();
}

async function ask(text) {
  busy = true; send.disabled = true;
  addMsg("user", text);
  const bot = addMsg("bot", "…");
  let answer = "";
  try {
    const r = await fetch("api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, model: $("model").value, effort: $("effort").value, history }),
    });
    if (!r.ok) throw new Error(r.status === 429 ? "Rate or daily limit reached. Try again later." : `Request failed (${r.status}).`);
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, i).replace(/^data: /, ""); buf = buf.slice(i + 2);
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.type === "sources") renderSources(bot, ev.sources);
        else if (ev.type === "delta") {
          answer += ev.text;
          bot.firstChild && bot.firstChild.nodeType === 3 ? (bot.firstChild.nodeValue = answer) : bot.prepend(answer);
        } else if (ev.type === "notice") bot.prepend(ev.text);
        else if (ev.type === "error") { bot.classList.add("err"); bot.prepend(ev.text); }
        log.scrollTop = log.scrollHeight;
      }
    }
    if (answer) history.push({ role: "user", content: text }, { role: "assistant", content: answer });
  } catch (e) {
    bot.classList.add("err"); bot.textContent = e.message;
  } finally {
    busy = false; send.disabled = false; input.focus();
  }
}

$("form").addEventListener("submit", (e) => {
  e.preventDefault();
  const t = input.value.trim();
  if (!t || busy) return;
  input.value = "";
  ask(t);
});
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("form").requestSubmit(); }
});
$("clear").addEventListener("click", () => { history = []; log.textContent = ""; });
loadModels();
