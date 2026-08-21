"""Lab 4 — An Agent You Can Trust (LangGraph · interactive CLI tutor)

Modern AI Pro · Level 2 · AI Practitioner · Day 3

    python labs/lab_4.py

A chatbot answers; an agent ACTS. This lab builds the acting kind the
production way, on LangGraph: tools the model chooses, a graph you can point
at, agentic RAG that checks its own retrieval, a budget cap so loops cannot
run away — and the checkpoint that makes it shippable: destructive actions
PAUSE for a human.

Builds on Lab 3's store (the corpus embeds once at start — one metered call).
Enter runs each stage · s skips · q quits. Piped input auto-runs (CI-safe).
"""

import json
import sys

from _kit import Stage, banner, chat, client, meter, say, stages, MODEL
from lab_3 import CORPUS_DIR, STORE, chunk, embed, retrieve

# ── the tools ────────────────────────────────────────────────────────────────
# Three tools, three risk tags. The tag is STRUCTURAL — it travels with the
# tool, not the prompt, so no clever wording can talk the agent past it.

TICKETS: list[dict] = []  # our pretend ticketing system


def search_policies(cli, query: str) -> str:
    chunks = retrieve(cli, query, k=3)
    return "\n\n".join(f"({c['doc']}) {c['text']}" for c in chunks)


def calc(expression: str) -> str:
    if not all(ch in "0123456789.+-*/() " for ch in expression):
        return "error: only arithmetic allowed"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))  # noqa: S307 — charset-fenced above
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


def file_ticket(title: str, body: str) -> str:
    TICKETS.append({"id": f"T-{len(TICKETS)+1:03}", "title": title, "body": body})
    return f"filed {TICKETS[-1]['id']}: {title}"


RISK = {"search_policies": "read", "calc": "read", "file_ticket": "destructive"}

TOOLS_SPEC = [
    {"type": "function", "function": {
        "name": "search_policies",
        "description": "Search Meridian Corp's policy corpus. Returns cited excerpts.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "calc",
        "description": "Evaluate an arithmetic expression, e.g. per-diem math.",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                       "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "file_ticket",
        "description": "File a helpdesk ticket on the employee's behalf. THIS ACTS.",
        "parameters": {"type": "object", "properties": {"title": {"type": "string"},
                                                        "body": {"type": "string"}},
                       "required": ["title", "body"]}}},
]

SYSTEM = ("You are Meridian's helpdesk agent. Ground every policy claim in "
          "search_policies results. Use calc for arithmetic. Only file_ticket when "
          "the user asks for an action. Be concise.")


def run_tool(cli, name: str, args: dict) -> str:
    if name == "search_policies":
        return search_policies(cli, args.get("query", ""))
    if name == "calc":
        return calc(args.get("expression", ""))
    if name == "file_ticket":
        return file_ticket(args.get("title", ""), args.get("body", ""))
    return f"error: unknown tool {name}"


# ── the graph ────────────────────────────────────────────────────────────────
# State is a plain dict — no framework message classes, so you can read every
# hop. Nodes take state, return the fields they changed. LangGraph wires the
# loop: agent → (tools? gate? end) → agent …

from typing import TypedDict  # noqa: E402

from langgraph.graph import END, START, StateGraph  # noqa: E402


class State(TypedDict, total=False):
    messages: list
    calls: int
    budget: int
    approve_all: bool


def make_app(cli):
    def agent(state: State) -> State:
        if state["calls"] >= state["budget"]:
            say(f"  [red]⛔ budget cap: {state['budget']} model calls — stopping honestly[/red]")
            return {"messages": state["messages"] + [
                {"role": "assistant",
                 "content": "I hit my step budget before finishing — a human should take over."}]}
        resp = cli.chat.completions.create(
            model=MODEL, messages=state["messages"], tools=TOOLS_SPEC, max_tokens=350)
        meter.add(resp.usage, "agent")
        msg = resp.choices[0].message
        entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = [
                {"id": t.id, "type": "function",
                 "function": {"name": t.function.name, "arguments": t.function.arguments}}
                for t in msg.tool_calls]
        return {"messages": state["messages"] + [entry], "calls": state["calls"] + 1}

    def tools(state: State) -> State:
        out = state["messages"][:]
        for t in state["messages"][-1]["tool_calls"]:
            name, args = t["function"]["name"], json.loads(t["function"]["arguments"] or "{}")
            risk = RISK.get(name, "unknown")
            say(f"    [yellow]→ tool {name}[/yellow] [dim]({risk}) {str(args)[:70]}[/dim]")
            if risk == "destructive":
                ok = state.get("approve_all") or approve(name, args)
                if not ok:
                    out.append({"role": "tool", "tool_call_id": t["id"],
                                "content": "DENIED by human reviewer. Do not retry; "
                                           "tell the user it needs manual action."})
                    say("    [red]✋ held at the checkpoint — denied[/red]")
                    continue
                say("    [green]✓ approved at the checkpoint[/green]")
            out.append({"role": "tool", "tool_call_id": t["id"],
                        "content": run_tool(cli, name, args)})
        return {"messages": out}

    def route(state: State) -> str:
        return "tools" if state["messages"][-1].get("tool_calls") else "end"

    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", tools)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "end": END})
    g.add_edge("tools", "agent")
    return g.compile()


def approve(name: str, args: dict) -> bool:
    """The HITL checkpoint. Piped runs default to DENY — fail closed."""
    if not sys.stdin.isatty():
        say("    [dim](non-interactive → fail closed, denying)[/dim]")
        return False
    ans = input(f"    ✋ HITL: allow {name}({json.dumps(args)[:60]})? [y/N] > ").strip().lower()
    return ans.startswith("y")


def run(cli, app, question: str, budget: int = 6, approve_all: bool = False) -> None:
    say(f"  [bold]you:[/bold] {question}")
    final = app.invoke({"messages": [{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": question}],
                        "calls": 0, "budget": budget, "approve_all": approve_all},
                       {"recursion_limit": 25})
    say(f"  [bold]agent:[/bold] {final['messages'][-1]['content']}\n")


# ── stages ───────────────────────────────────────────────────────────────────

def stage_build(cli):
    for f in sorted(CORPUS_DIR.glob("*.md")):
        for c in chunk(f.read_text()):
            STORE.append({"doc": f.name, "text": c, "vec": None})
    vecs = embed(cli, [c["text"] for c in STORE])
    for c, v in zip(STORE, vecs):
        c["vec"] = v
    say(f"  Lab 3's store rebuilt: {len(STORE)} chunks embedded (one call).\n")
    say("An agent is three things a chatbot isn't: TOOLS it may call, a LOOP that")
    say("feeds results back, and a STOP decision. You'll see all three as a graph:")
    say("  START → agent —(tool_calls?)→ tools → agent … —(no)→ END")


def stage_first_tool(cli):
    say("The model doesn't run tools — it ASKS for them in structured output")
    say("(Lab 1 stage 2, all grown up). Watch the loop think:\n")
    run(cli, make_app(cli), "What's the meal cap for a 3-day domestic trip, total? Use the policy and do the math.")
    say("Two tools, chosen and sequenced by the model, results fed back — that")
    say("loop is the whole trick. Everything else this lab adds is TRUST.")


def stage_agentic_rag(cli):
    say("Agentic RAG = the agent treats retrieval as a tool it can RE-AIM. A vague")
    say("question forces a second, sharper search:\n")
    run(cli, make_app(cli), "Someone from outside the company needs to get into our systems for a project — what rules apply?")
    say("Single-shot RAG retrieves once and hopes (Lab 3). The agent judged its own")
    say("results and searched again with better words — sufficiency, self-checked.")


def stage_budget(cli):
    say("Loops run away — a cap makes failure honest instead of expensive.")
    say("Same agent, budget of TWO model calls:\n")
    run(cli, make_app(cli), "Compare travel, procurement and AI policies for anything that mentions approvals, then summarize each.", budget=2)
    say("It stopped, said so, and handed off — that beats a 40-call bill every time.")
    say("Budgets, timeouts and caps are to agents what brakes are to cars.")


def stage_hitl(cli):
    say("The agent can ACT (file_ticket) — and acting is where trust is earned.")
    say("file_ticket is tagged DESTRUCTIVE, so the graph pauses for a human:\n")
    run(cli, make_app(cli), "My laptop dock is broken — file a ticket for IT to replace it.")
    say(f"  tickets filed this session: {TICKETS or 'none'}\n")
    say("You just were the checkpoint. The tag lives on the TOOL (structural),")
    say("the default is FAIL CLOSED, and a denial becomes honest feedback to the")
    say("agent — the three rules that make HITL real instead of theater.")


if __name__ == "__main__":
    banner("Level 2 · AI Practitioner · Day 3", "Lab 4 · An Agent You Can Trust")
    cli = client()
    stages(cli, [
        Stage("Rebuild the store — the agent's knowledge tool",
              why="An agent differs from a chatbot in three ways: TOOLS it may "
                  "call, a LOOP that feeds results back, and a STOP decision. "
                  "Lab 3's retrieval becomes tool #1 — same code, new caller: "
                  "now the MODEL decides when to search. The graph makes the "
                  "loop explicit: START → agent —tool_calls?→ tools → agent … "
                  "→ END. If you can't draw it, you can't audit it.",
              fn=stage_build,
              logic="The store is up and the loop is on the table. Keep the "
                    "graph picture in view for every stage: each one changes "
                    "exactly one thing about it — what tools exist, how routing "
                    "decides, when it stops, and who must approve."),
        Stage("First tool call — watch the loop think",
              why="The model never runs code — it EMITS a structured request "
                  "(Lab 1's JSON, grown up) naming a tool and arguments; your "
                  "code runs it and feeds the result back; the model continues. "
                  "The question needs policy lookup AND arithmetic, so a real "
                  "plan requires sequencing two different tools.",
              fn=stage_first_tool,
              logic="The model chose the tools, the order, and when to stop — "
                    "given only descriptions of what each tool does. That's why "
                    "tool descriptions are load-bearing prompts, not comments. "
                    "And note who held the actual capability: your code. The "
                    "model requests; the harness decides — that separation is "
                    "where every safety property lives."),
        Stage("Agentic RAG — retrieval that re-aims itself",
              why="Lab 3's pipeline retrieves once and hopes — a vague question "
                  "retrieves vaguely and the answer inherits the miss. An agent "
                  "can JUDGE its own results and search again with better "
                  "words. Ask something fuzzy and count the searches.",
              fn=stage_agentic_rag,
              logic="The re-aim is sufficiency checking: the agent compared what "
                    "it got against what the question needs — a self-eval in "
                    "the loop, which is Lab 3's judge idea applied to its own "
                    "work-in-progress. The trade: better answers for more "
                    "calls. Which is exactly why the next stage exists."),
        Stage("The budget cap — honest failure",
              why="A loop that decides its own next step can decide to loop "
                  "forever — and each lap costs money (Lab 1's meter). Lab 1's "
                  "timeout bounded ONE call; an agent needs the same brake at "
                  "the loop level. Give it a big task and 2 calls and watch "
                  "what running out looks like.",
              fn=stage_budget,
              logic="It stopped AND SAID SO — handing off honestly instead of "
                    "silently burning 40 calls. An unbounded agent isn't more "
                    "capable, it's more expensive at failing. Caps, timeouts "
                    "and budgets are to agents what brakes are to cars: the "
                    "feature that makes speed usable."),
        Stage("The HITL checkpoint — destructive means pause",
              why="Reading is reversible; ACTING is not — and 'the prompt says "
                  "be careful' is not a control, because prompts can be talked "
                  "around. The risk tag lives on the TOOL (structural, "
                  "unpromptable), routing every destructive call through a "
                  "human. Piped runs auto-DENY: fail closed, like Lab 2's gate.",
              fn=stage_hitl,
              logic="Three rules made that real rather than theater: the tag is "
                    "structural (no wording bypasses it) · the default is DENY "
                    "(a broken checkpoint blocks, never admits) · the denial "
                    "returned as feedback, so the agent explained instead of "
                    "retrying. Autonomy is earned action-by-action — this "
                    "checkpoint is how."),
    ])
    meter.show()
