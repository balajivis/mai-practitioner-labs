"""Shared plumbing for the Level 2 labs — deliberately small and readable.

Everything here is glass-box: open it. The labs import four things —

    client()   an OpenAI client pointed at the class proxy (your .env)
    stages()   the interactive tutor loop: Enter runs a stage, s skips, q quits;
               piped/non-interactive input auto-runs everything (CI-safe)
    say/rule   rich console helpers
    meter      running token/call tally for the session (the cost habit)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()
say = console.print


def rule(title: str) -> None:
    say(Rule(f"[bold]{title}[/bold]", style="yellow"))


def banner(course_line: str, title: str) -> None:
    say(Panel.fit(f"[bold]{course_line}[/bold]\n{title}", border_style="yellow"))


# ── env + client ─────────────────────────────────────────────────────────────

def client() -> OpenAI:
    """Load .env and return a client on the class proxy. Fails with the fix, not a trace.

    MAI_API_KEY is accepted as an alias: the Practice page names that variable
    (it's what the Level 1 kit reads), so a student who follows the page instead
    of the .env comment still works rather than hitting a confusing error."""
    load_dotenv()
    key = (os.environ.get("OPENAI_API_KEY", "") or os.environ.get("MAI_API_KEY", "")).strip()
    if not key or key.startswith("paste-your"):
        say(
            "\n[red]✗ No key found.[/red] Copy .env.example to .env, mint your key at\n"
            "  [bold]https://study.modernaipro.com/practice[/bold] "
            "(button: 'Get my practice key')\n  and paste it into OPENAI_API_KEY.\n"
        )
        sys.exit(1)
    os.environ["OPENAI_API_KEY"] = key  # the SDK reads this one
    if not os.environ.get("OPENAI_BASE_URL", "").strip():
        os.environ["OPENAI_BASE_URL"] = "https://learn.modernaipro.com/api/llm/v1"
        say("[dim](no OPENAI_BASE_URL in .env — defaulting to the class proxy)[/dim]")
    return OpenAI()


MODEL = "mai"  # the proxy picks the class model; this value is ignored by design


# ── the session meter ────────────────────────────────────────────────────────

@dataclass
class Meter:
    """Running cost awareness. Every helper below feeds it; print it any time."""
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    by_label: dict = field(default_factory=dict)

    def add(self, usage, label: str = "call") -> None:
        if not usage:
            return
        self.calls += 1
        self.prompt_tokens += usage.prompt_tokens or 0
        self.completion_tokens += usage.completion_tokens or 0
        row = self.by_label.setdefault(label, [0, 0])
        row[0] += 1
        row[1] += (usage.total_tokens or 0)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def show(self) -> None:
        parts = " · ".join(f"{k} ×{v[0]} ({v[1]} tok)" for k, v in self.by_label.items())
        say(f"[dim]meter: {self.calls} calls · {self.total_tokens} tokens — {parts}[/dim]")


meter = Meter()


def chat(cli: OpenAI, messages: list[dict], label: str = "chat", **kw) -> str:
    """One metered chat call. kw passes through (max_tokens, response_format, ...).
    Waits out a burst-limit 429 once — eval suites are bursty by nature."""
    import time as _time
    for attempt in (1, 2):
        try:
            resp = cli.chat.completions.create(model=MODEL, messages=messages, **kw)
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 1 and "429" in str(e):
                say("[dim](burst limit — waiting 25s, this is the shared classroom lane)[/dim]")
                _time.sleep(25)
                continue
            raise
    meter.add(resp.usage, label)
    return (resp.choices[0].message.content or "").strip()


def stream_chat(cli: OpenAI, messages: list[dict], label: str = "stream",
                on_delta=None, **kw) -> str:
    """Streamed chat that degrades honestly.

    Two ways a proxy can fail to stream, and we handle BOTH: it can raise, or it
    can quietly answer a stream request with a normal JSON body (the SDK then
    iterates zero chunks and you'd see a blank screen). If no text arrives, we
    say so and re-ask without streaming — the lesson survives either way."""
    out: list[str] = []
    try:
        stream = cli.chat.completions.create(model=MODEL, messages=messages,
                                             stream=True, **kw)
        usage = None
        for part in stream:
            if getattr(part, "usage", None):
                usage = part.usage
            delta = part.choices[0].delta.content if (part.choices and part.choices[0].delta) else None
            if delta:
                out.append(delta)
                if on_delta:
                    on_delta(delta)
        if out:
            meter.add(usage, label) if usage else setattr(meter, "calls", meter.calls + 1)
            return "".join(out)
    except Exception:  # noqa: BLE001 — transport hiccup, or a proxy that rejects stream=
        pass
    say("\n  [dim](this proxy build answered without streaming — same text, "
        "delivered all at once)[/dim]\n  ")
    text = chat(cli, messages, label=label, **kw)
    if on_delta:
        on_delta(text)
    return text


# ── the tutor loop ───────────────────────────────────────────────────────────
# Every stage teaches in the same shape, on purpose:
#
#   WHY        the reasoning — what problem exists and why you should care,
#              BEFORE any code runs (so you know what to watch for)
#   the demo   the fn — code + live model calls you can read and rerun
#   THE LOGIC  what the observation you just made PROVES, and the rule
#              you can carry to your own systems
#
# Claim → evidence → conclusion. If a stage can't fill all three, it isn't
# teaching — that's the bar for adding one.

@dataclass
class Stage:
    title: str
    why: str          # the reasoning, shown before the demo
    fn: object        # callable(cli) — the demonstration
    logic: str        # the conclusion the evidence supports, shown after


def stages(cli: OpenAI, steps: list[Stage]) -> None:
    """Run Stage(title, why, fn, logic) steps. Interactive: Enter/s/q. Piped: auto-run."""
    interactive = sys.stdin.isatty()
    for i, st in enumerate(steps, 1):
        rule(f"Stage {i}/{len(steps)} · {st.title}")
        say(Panel(st.why.strip(), title="[bold]why[/bold]", title_align="left",
                  border_style="blue", padding=(0, 2)))
        if interactive:
            ans = input("  Enter to run · s skip · q quit > ").strip().lower()
            if ans == "q":
                break
            if ans == "s":
                continue
        st.fn(cli)
        say(Panel(st.logic.strip(), title="[bold]the logic[/bold]", title_align="left",
                  border_style="green", padding=(0, 2)))
        meter.show()
    say()
    say(Panel.fit("[bold green]Lab complete.[/bold green] git pull before the next session.",
                  border_style="green"))


def ask_yn(prompt: str, default: bool = True) -> bool:
    """Interactive yes/no; piped input takes the default (CI-safe)."""
    if not sys.stdin.isatty():
        return default
    ans = input(f"  {prompt} [{'Y/n' if default else 'y/N'}] > ").strip().lower()
    if not ans:
        return default
    return ans.startswith("y")
