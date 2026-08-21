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

from _kit import Stage, banner, chat, client, meter, say, stages, stream_chat


# ── Stage 1 · the anatomy of a call ─────────────────────────────────────────

def stage_first_call(cli):
    say("A chat call is a LIST OF MESSAGES with roles. The system message is the")
    say("steering wheel — same question, two systems:\n")
    q = "What should our team do about flaky tests?"
    for persona in (
        "You are a staff SRE talking to engineers. Two sentences, name specific "
        "technical tactics, use the jargon.",
        "You are a CFO talking to the board. Two sentences, NO engineering jargon "
        "at all — speak only about cost, risk and delivery dates.",
    ):
        out = chat(cli, [
            {"role": "system", "content": persona},
            {"role": "user", "content": q},
        ], label="roles", max_tokens=120)
        say(f"  [yellow]system:[/yellow] [dim]{persona[:64]}…[/dim]")
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
        Stage("The anatomy of a call — roles steer",
              why="An LLM call has no 'settings panel' — the message list IS the "
                  "configuration. If the system role really steers behaviour, then "
                  "two different system messages with an identical question must "
                  "produce visibly different answers. That's a testable claim.",
              fn=stage_first_call,
              logic="Same model, same question, different system message → different "
                    "behaviour. Therefore behaviour lives in the prompt, not the "
                    "model. Corollary: prompts are code — version them, review "
                    "them, and never let 'just tweak the prompt' skip review."),
        Stage("Structured output — JSON a program can parse",
              why="Programs can't branch on prose. For an LLM to sit INSIDE a "
                  "system (not just chat with a human), its output must be "
                  "machine-checkable. The test: extract fields from messy text "
                  "and have json.loads — not a human — decide if it worked.",
              fn=stage_structured,
              logic="The parse succeeding is the point: correctness became a "
                    "mechanical check. This is the foundational move of the whole "
                    "weekend — Lab 3's judge verdicts and Lab 4's tool calls are "
                    "this same pattern with higher stakes. Rule: schema + "
                    "response_format + parse-or-fail, never 'hope it's JSON'."),
        Stage("Streaming — latency users forgive",
              why="Total generation time is roughly fixed by output length — you "
                  "can't make the model finish much faster. But perceived latency "
                  "is time-to-FIRST-token. If tokens arrive as they're generated, "
                  "the wait users actually feel shrinks by 10x.",
              fn=stage_streaming,
              logic="You optimized nothing about the model, only WHERE the waiting "
                    "happens — and that's the lever you control. Rule: any "
                    "user-facing generation over ~2s streams; batch jobs never "
                    "need to."),
        Stage("Failure is normal — timeout · retry · backoff",
              why="Networks drop, providers rate-limit, models time out — at "
                  "1,000 calls/day even a 1% failure rate is 10 daily failures. "
                  "So reliability can't come from hoping calls succeed; it must "
                  "come from what your code does when they don't.",
              fn=stage_failures,
              logic="Timeout bounds the damage, retry absorbs the transient, "
                    "backoff (doubling waits) keeps your retries from becoming "
                    "the flood that keeps the service down. When retries run "
                    "out: honest error, never a hang. That four-part shape is "
                    "universal — you'll meet it again as the agent budget cap."),
        Stage("The cost meter — know your number",
              why="Token costs are invisible per-call and shocking per-month — "
                  "the classic failure is discovering the bill AFTER launch. The "
                  "meter you've been feeding all lab exists to make cost a "
                  "number you check WHILE building, like a test.",
              fn=stage_cost,
              logic="Cost per feature = tokens/call × calls/session × sessions — "
                    "three numbers you now measure, not guess. Input tokens "
                    "usually dominate (context is the cost driver), and history "
                    "resends make chat cost climb every turn: watch that bite "
                    "in Lab 2. Budget per feature before you ship it."),
    ])
