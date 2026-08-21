"""Lab 1 — LLM Calls Done Right (interactive CLI tutor)

Modern AI Pro · Level 2 · AI Practitioner · Day 1

    python labs/lab_1.py

You have called an LLM before. This lab is about calling one like a
practitioner: roles that steer, structured output a program can parse,
streaming a user can watch, failure handling that survives the real world —
and a running COST METER, because you are on your own metered key and
"what does this feature cost per call?" is a question you will now always
be able to answer.

Enter runs each stage · s skips · q quits. Piped input auto-runs (CI-safe).
"""

import json
import time

from _kit import banner, chat, client, meter, say, stages, stream_chat


# ── Stage 1 · the anatomy of a call ─────────────────────────────────────────

def stage_first_call(cli):
    say("A chat call is a LIST OF MESSAGES with roles. The system message is the")
    say("steering wheel — same question, two systems:\n")
    q = "What should our team do about flaky tests?"
    for persona in (
        "You are a terse engineering lead. Answer in two sentences, concretely.",
        "You are a cheerful motivational coach. Answer in two sentences.",
    ):
        out = chat(cli, [
            {"role": "system", "content": persona},
            {"role": "user", "content": q},
        ], label="roles", max_tokens=120)
        say(f"  [yellow]system:[/yellow] [dim]{persona[:58]}…[/dim]")
        say(f"  [green]→[/green] {out}\n")
    say("Same model, same question — the system role did all the work. Every app")
    say("you build this weekend starts by writing that message deliberately.")


# ── Stage 2 · structured output ─────────────────────────────────────────────

def stage_structured(cli):
    say("Prose is for humans; programs need FIELDS. Ask for JSON and parse it:\n")
    out = chat(cli, [
        {"role": "system", "content":
            "Extract from the user's text. Respond with ONLY a JSON object: "
            '{"name": str, "level": str, "topics": [str], "sentiment": "pos"|"neg"|"neutral"}'},
        {"role": "user", "content":
            "Hi, I'm Priya — loved the RAG session in Level 2, though the eval part moved fast."},
    ], label="structured", max_tokens=150, response_format={"type": "json_object"})
    say(f"  raw: [dim]{out}[/dim]")
    cleaned = out.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(cleaned)
    say(f"  parsed → name=[bold]{data.get('name')}[/bold] · topics={data.get('topics')} "
        f"· sentiment={data.get('sentiment')}\n")
    say("`response_format=json_object` + a schema in the system message is the")
    say("workhorse. This exact shape becomes TOOL CALLING in Lab 4 — an agent is")
    say("a model whose structured output names the next function to run.")


# ── Stage 3 · streaming ─────────────────────────────────────────────────────

def stage_streaming(cli):
    say("Users forgive latency they can WATCH. Stream tokens as they arrive:\n  ")
    stream_chat(cli, [{"role": "user", "content":
                       "In three short sentences: why do users prefer streamed responses?"}],
                max_tokens=120, on_delta=lambda d: say(d, end=""))
    say("\n\nTime-to-first-token is the UX number that matters; total time barely does.")


# ── Stage 4 · failure is normal ─────────────────────────────────────────────

def stage_failures(cli):
    say("Production calls fail: timeouts, rate limits, transient 5xx. The pattern")
    say("is always the same — TIMEOUT + RETRY with BACKOFF:\n")
    bounded = cli.with_options(timeout=20.0, max_retries=0)  # we drive retries ourselves
    for attempt in range(1, 4):
        try:
            out = chat(bounded, [{"role": "user", "content": "Reply with exactly: RESILIENT"}],
                       label="retry", max_tokens=10)
            say(f"  attempt {attempt}: [green]{out}[/green]")
            break
        except Exception as e:  # noqa: BLE001 — the demo point is the shape
            wait = 2 ** attempt
            say(f"  attempt {attempt} failed ({type(e).__name__}) — backing off {wait}s")
            time.sleep(wait)
    else:
        say("  [red]all retries exhausted — surface an honest error to the user[/red]")
    say("\nThe SDK can do this for you (`max_retries`), but you just built the loop")
    say("it runs — and you know why the waits double.")


# ── Stage 5 · the cost meter ────────────────────────────────────────────────

def stage_cost(cli):
    say("Every stage fed the meter from the provider's REAL usage numbers:\n")
    meter.show()
    say("\nRules of thumb you can now verify instead of guess:")
    say("  · input tokens usually dwarf output — context is the cost driver")
    say("  · a chatbot RESENDS its history every turn (watch this bite in Lab 2)")
    say("  · budget per FEATURE, not per month: tokens/call × calls/user × users")
    verdict = chat(cli, [{"role": "user", "content":
        f"A feature uses ~{max(meter.total_tokens, 1)} tokens per user session. "
        "In two sentences, is that cheap or expensive at 10k daily users, and why?"}],
        label="estimate", max_tokens=300)
    say(f"\n  [green]model's own estimate:[/green] {verdict}")
    say("\nYour key's lifetime usage is on your Practice page — check it after class.")


if __name__ == "__main__":
    banner("Level 2 · AI Practitioner · Day 1", "Lab 1 · LLM Calls Done Right")
    cli = client()
    stages(cli, [
        ("The anatomy of a call — roles steer", stage_first_call),
        ("Structured output — JSON a program can parse", stage_structured),
        ("Streaming — latency users forgive", stage_streaming),
        ("Failure is normal — timeout · retry · backoff", stage_failures),
        ("The cost meter — know your number", stage_cost),
    ])
