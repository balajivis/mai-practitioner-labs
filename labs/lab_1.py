"""Lab 1 — Evaluation First · setup check

Modern AI Pro · Level 2 · AI Practitioner

    python labs/lab_1.py

Tonight this is your READINESS CHECK: it proves Python, the install, and your
key in one shot. The full Lab 1 — golden cases, the judge, the baseline every
later lab must beat — ships into this same file for Friday's class; run
`git pull` before the session.
"""

import os
import sys

try:
    from dotenv import load_dotenv
    from openai import OpenAI
    from rich.console import Console
    from rich.panel import Panel
except ImportError as e:
    print(f"\n  Missing dependency ({e.name}). From the repo root, run:")
    print("    pip install -r requirements.txt\n")
    sys.exit(1)

console = Console()


def main() -> None:
    console.print(Panel.fit(
        "[bold]Level 2 · AI Practitioner[/bold]\nLab 1 · Evaluation First — setup check",
        border_style="yellow",
    ))

    load_dotenv()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    base = os.environ.get("OPENAI_BASE_URL", "").strip()

    if not key or key.startswith("paste-your"):
        console.print(
            "\n[red]✗ No key found.[/red] Copy .env.example to .env, then mint your key at\n"
            "  [bold]https://study.modernaipro.com/practice[/bold] and paste it into OPENAI_API_KEY.\n"
        )
        sys.exit(1)
    console.print(f"  ✓ .env loaded — key [dim]{key[:8]}…[/dim]")
    if base:
        console.print(f"  ✓ proxy [dim]{base}[/dim]")

    console.print("  … calling the class model", end="")
    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model="mai",  # the proxy picks the class model; this value is ignored
            messages=[{"role": "user", "content": "Reply with exactly: READY"}],
            max_tokens=10,
        )
    except Exception as e:  # noqa: BLE001 — any failure here is a setup problem
        console.print(f"\n[red]✗ The model call failed:[/red] {e}")
        console.print(
            "\n  Usual suspects: a typo in the key (re-mint at /practice — the old key\n"
            "  stops working), or a missing OPENAI_BASE_URL line (see .env.example).\n"
        )
        sys.exit(1)

    reply = (resp.choices[0].message.content or "").strip()
    used = resp.usage.total_tokens if resp.usage else "?"
    console.print(f"\r  ✓ key accepted — model [bold]{resp.model}[/bold] replied "
                  f"[green]{reply}[/green] ({used} tokens, metered to your budget)")

    console.print(Panel.fit(
        "[bold green]You are ready for Level 2.[/bold green]\n\n"
        "Friday 4:30 PM PT · Lab 1 · Evaluation First:\n"
        "you'll build a real RAG, author golden test cases, and set the baseline\n"
        "score every later lab has to beat.\n\n"
        "[dim]git pull before each session — labs ship here over the weekend.[/dim]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
