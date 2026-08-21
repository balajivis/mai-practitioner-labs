"""Lab 5 — Compose & Ship (the capstone)

Modern AI Pro · Level 2 · AI Practitioner · Day 3

    python labs/lab_5.py

Labs 1–4 built the parts; this lab snaps them into ONE product — a Meridian
helpdesk app in Gradio: chat UI (Lab 2), every policy answer grounded with
citations (Lab 3), tool-use + HITL approval routed through the agent graph
(Lab 4), and the cost meter from Lab 1 live in the corner.

Run it, break it, demo it to your pair. Then swap the corpus/ folder for
documents from YOUR world — that version is your portfolio piece.

Headless check (CI-safe):  piped input answers one scripted question and exits.
"""

import sys

from _kit import banner, client, meter, say
from lab_3 import CORPUS_DIR, STORE, chunk, embed
import lab_4


def build_store(cli) -> None:
    for f in sorted(CORPUS_DIR.glob("*.md")):
        for c in chunk(f.read_text()):
            STORE.append({"doc": f.name, "text": c, "vec": None})
    vecs = embed(cli, [c["text"] for c in STORE])
    for c, v in zip(STORE, vecs):
        c["vec"] = v
    say(f"  store ready: {len(STORE)} chunks")


def make_respond(cli, app):
    """One entry point: every user turn goes through the AGENT graph, which
    decides for itself whether to search, calculate, act — or just talk."""
    def respond(message, ui_history):
        messages = [{"role": "system", "content": lab_4.SYSTEM}]
        for u, a in ui_history:
            messages += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": message})
        final = app.invoke(
            {"messages": messages, "calls": 0, "budget": 6,
             # In the UI the terminal isn't watchable mid-request, so destructive
             # tools are auto-DENIED (fail closed). Approving from the UI itself
             # is the classic extension — build it and show your pair.
             "approve_all": False},
            {"recursion_limit": 25})
        reply = final["messages"][-1]["content"]
        return f"{reply}\n\n—\n`{meter.calls} calls · {meter.total_tokens} tokens this session`"
    return respond


if __name__ == "__main__":
    banner("Level 2 · AI Practitioner · Day 3", "Lab 5 · Compose & Ship — the capstone")
    cli = client()
    build_store(cli)
    app = lab_4.make_app(cli)
    respond = make_respond(cli, app)

    if not sys.stdin.isatty():
        # headless: one scripted end-to-end turn proves the composition works
        say("\n[dim]headless check:[/dim]")
        out = respond("What needs to happen before I buy a $30k analytics SaaS?", [])
        say(f"  {out}")
        meter.show()
        sys.exit(0)

    try:
        import gradio as gr
    except ImportError:
        say("[red]gradio isn't installed[/red] — `pip install gradio`, then rerun.")
        sys.exit(1)

    say("\n  [bold]Why this lab exists:[/bold] parts are not a product. Labs 1–4 each")
    say("  proved one component; composition is where the real questions appear —")
    say("  which component answers which turn, where the meters aggregate, where")
    say("  the checkpoint sits when a UI (not a terminal) is in front. One agent")
    say("  graph routes EVERY turn: it decides chat vs search vs act, per message.")
    say("\n  Try these, in order — each exercises a different lab:")
    say("   · How do I file a travel expense?                  (chat + RAG + citations)")
    say("   · $75/day for 4 days minus a $40 dinner — total?   (tool: calc)")
    say("   · File a ticket: my badge stopped working.          (HITL — watch it hold)")
    say("  [dim]Ctrl-C stops the server. Swap corpus/ for your own docs after class.[/dim]\n")
    gr.ChatInterface(make_respond(cli, app),
                     title="Meridian Helpdesk — Labs 1–4, composed").launch()
