import os
import gradio as gr
import litellm

from guardrails.pipeline import GuardrailPipeline

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ollama/llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
SYSTEM_PROMPT = "Você é um assistente útil e responsável."

pipeline = GuardrailPipeline()


# ── Guardrail HTML renderer ─────────────────────────────────────────────────

_CSS = """
<style>
.gr-container{font-family:system-ui,sans-serif;font-size:14px}
.status{padding:10px 16px;border-radius:8px;font-weight:700;font-size:15px;
        text-align:center;margin-bottom:14px;letter-spacing:.5px}
.status.blocked{background:#ef4444;color:#fff}
.status.warning{background:#d97706;color:#fff}
.status.safe{background:#16a34a;color:#fff}
.card{background:rgba(128,128,128,0.15);border:1px solid rgba(128,128,128,0.25);
      border-radius:8px;padding:12px 14px;margin-bottom:12px}
.card h4{margin:0 0 8px;font-size:12px;opacity:.7;text-transform:uppercase;
         letter-spacing:.6px}
.bar-bg{background:rgba(128,128,128,0.3);border-radius:4px;height:10px;margin:6px 0}
.bar-fill{height:10px;border-radius:4px}
.pill{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;
      font-weight:600;margin:2px}
.pill.red{background:rgba(239,68,68,0.25);color:#f87171}
.pill.yellow{background:rgba(217,119,6,0.25);color:#fbbf24}
.pill.green{background:rgba(22,163,74,0.25);color:#4ade80}
.entity-list{margin:4px 0 0;padding-left:16px;font-size:13px;opacity:.85}
.prompt-box{background:rgba(0,0,0,0.2);border:1px solid rgba(128,128,128,0.25);
            border-radius:6px;padding:8px 10px;font-family:monospace;font-size:12px;
            white-space:pre-wrap;margin-top:6px}
.dim{opacity:.55;font-size:13px}
</style>
"""


def _score_color(score: float) -> str:
    if score >= 0.7:
        return "#ef4444"
    if score >= 0.3:
        return "#f59e0b"
    return "#22c55e"


def _render_guardrail_html(analysis: dict) -> str:
    blocked = analysis["blocked"]
    pii_found = analysis["pii"]["found"]

    if blocked:
        status = '<div class="status blocked">🚫 BLOQUEADO</div>'
    elif pii_found:
        status = '<div class="status warning">⚠️ PII MASCARADO</div>'
    else:
        status = '<div class="status safe">✅ SEGURO</div>'

    # Toxicity card
    tox = analysis["toxicity"]
    tox_score = tox.get("score", 0)
    bar_color = _score_color(tox_score)
    tox_label = "🔴 TÓXICO" if tox.get("is_toxic") else "🟢 OK"

    top_categories = sorted(
        ((k, v) for k, v in tox.get("scores", {}).items() if v >= 0.1),
        key=lambda x: -x[1],
    )
    category_html = "".join(
        f'<div style="display:flex;justify-content:space-between;font-size:12px;'
        f'color:#6b7280;margin:2px 0"><span>{k}</span><span>{v:.3f}</span></div>'
        for k, v in top_categories
    ) or '<span class="dim">Nenhuma categoria acima de 0.1</span>'

    tox_card = f"""
    <div class="card">
      <h4>Toxicidade — {tox_label}</h4>
      <div class="bar-bg">
        <div class="bar-fill" style="width:{tox_score*100:.1f}%;background:{bar_color}"></div>
      </div>
      <div style="text-align:right;font-size:12px;color:#6b7280">score: <strong>{tox_score:.3f}</strong></div>
      {category_html}
    </div>
    """

    # PII card
    entities = analysis["pii"]["entities"]
    if entities:
        pills = "".join(
            f'<span class="pill yellow">{e["type"]}</span>' for e in entities
        )
        entity_rows = "".join(
            f'<li><code>{e["value"]}</code> → <em>{e["type"]}</em> '
            f'({e["score"]:.0%})</li>'
            for e in entities
        )
        pii_body = f"""
        {pills}
        <ul class="entity-list">{entity_rows}</ul>
        """
    else:
        pii_body = '<span class="dim">✅ Nenhum dado sensível encontrado.</span>'

    pii_card = f"""
    <div class="card">
      <h4>Detecção de PII</h4>
      {pii_body}
    </div>
    """

    # Prompt sent card (only when not blocked)
    prompt_card = ""
    if not blocked:
        sanitized = analysis["sanitized_message"]
        original = analysis["original"]
        changed = sanitized != original
        note = "⚠️ PII foi mascarado antes do envio." if changed else "✅ Enviado sem alterações."
        prompt_card = f"""
        <div class="card">
          <h4>Prompt enviado ao LLM</h4>
          <div class="dim" style="margin-bottom:4px">{note}</div>
          <div class="prompt-box">{sanitized}</div>
        </div>
        """

    return f'{_CSS}<div class="gr-container">{status}{tox_card}{pii_card}{prompt_card}</div>'


_IDLE_HTML = (
    '<div style="text-align:center;color:#9ca3af;padding:32px;font-size:14px">'
    "Envie uma mensagem para ver a análise dos guardrails."
    "</div>"
)


# ── Chat handler ────────────────────────────────────────────────────────────

def respond(message: str, history: list, _log):
    message = message.strip()
    if not message:
        return history, _log

    analysis = pipeline.analyze(message)
    guardrail_html = _render_guardrail_html(analysis)

    if analysis["blocked"]:
        history = history + [{"role": "user", "content": message},
                              {"role": "assistant", "content": f"🚫 {analysis['block_reason']}"}]
        return history, guardrail_html

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": analysis["sanitized_message"]})

    try:
        response = litellm.completion(
            model=OLLAMA_MODEL,
            messages=messages,
            api_base=OLLAMA_BASE_URL,
        )
        bot_response = response.choices[0].message.content
    except Exception as exc:
        bot_response = f"⚠️ Erro ao conectar com o LLM: {exc}"

    history = history + [{"role": "user", "content": message},
                          {"role": "assistant", "content": bot_response}]
    return history, guardrail_html


# ── UI ──────────────────────────────────────────────────────────────────────

EXAMPLES = [
    "Olá! Como você pode me ajudar hoje?",
    "Meu CPF é 123.456.789-00 e meu email é joao@empresa.com",
    "I hate those people, they should all die and go to hell!",
    "What is machine learning and how does it work?",
    "Me liga no (11) 98765-4321, meu CNPJ é 12.345.678/0001-99",
    "You are the dumbest AI I've ever seen, kill yourself",
]

with gr.Blocks(title="Responsible AI Demo") as demo:
    gr.Markdown(
        """
# 🛡️ Responsible AI — Guardrails na Prática
Cada mensagem passa por dois guardrails antes de chegar ao LLM:
**1. Toxicidade** (Detoxify) → bloqueia conteúdo ofensivo
**2. PII** (Presidio) → mascara dados pessoais (CPF, CNPJ, email, telefone…)
"""
    )

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                height=480,
                label="Chat",
            )
            with gr.Row():
                msg_box = gr.Textbox(
                    placeholder="Digite sua mensagem…",
                    show_label=False,
                    scale=5,
                    submit_btn=False,
                )
                send_btn = gr.Button("Enviar ▶", variant="primary", scale=1)
            clear_btn = gr.Button("🗑 Limpar conversa", variant="secondary", size="sm")

        with gr.Column(scale=2):
            gr.Markdown("### 🔍 Monitor de Guardrails")
            guardrail_panel = gr.HTML(value=_IDLE_HTML)

    gr.Examples(
        examples=EXAMPLES,
        inputs=msg_box,
        label="Exemplos — clique para carregar",
    )

    # Wire up events
    def _submit(message, history, log):
        return respond(message, history, log)

    submit_kwargs = dict(
        fn=_submit,
        inputs=[msg_box, chatbot, guardrail_panel],
        outputs=[chatbot, guardrail_panel],
    )

    send_btn.click(**submit_kwargs).then(lambda: "", outputs=msg_box)
    msg_box.submit(**submit_kwargs).then(lambda: "", outputs=msg_box)
    clear_btn.click(lambda: ([], _IDLE_HTML), outputs=[chatbot, guardrail_panel])


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
