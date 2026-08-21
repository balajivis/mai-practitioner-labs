# Modern AI Pro — Level 2 · AI Practitioner Labs

The lab kit for the **AI Practitioner** weekend (Level 2 of the Modern AI Pro ladder).
Every hands-on session of the course runs from this one repo. Labs ship and update
**over the course via `git pull`** — clone once, pull each morning.

## Setup (~15 minutes, do this before Day 1)

```bash
git clone https://github.com/balajivis/mai-practitioner-labs.git
cd mai-practitioner-labs
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Then **mint your personal MAI key** at
[study.modernaipro.com/practice](https://study.modernaipro.com/practice) (it shows exactly
once) and paste it into `OPENAI_API_KEY` in your `.env`. A shared class token pinned in the
cohort room on class days works in the same slot.

**Smoke-test** — proves Python, the install, and your key in one shot:

```bash
python labs/lab_1.py
```

If it greets you and your key is accepted, you are ready for Level 2.

## The labs

Run in order; each builds on the prior one. *(Labs land here move-by-move over the
weekend — `git pull` at the start of every session.)*

| Day | Lab | Name | Status |
|---|---|---|---|
| 1 (Fri) | 1 | **Evaluation First** — golden cases, the judge, the baseline every later lab must beat | setup-check live · full lab ships Friday |
| 2 (Sat) | 2 | **Retrieval, Measured** — hybrid, metadata, rerank, contextual | ships via git pull |
| 2 (Sat) | 3 | **Agentic RAG** — router · query rewrite · decomposition · sufficiency · budget caps | ships via git pull |
| 2 (Sat) | 4 | **Memory & Personalization** | ships via git pull |
| 2 (Sat) | 5 | **The Calibrated Judge & the Eval Gate** | ships via git pull |
| 3 (Sun) | 6 | **Guardrails & Security** — the gauntlet, tenant ACLs | ships via git pull |
| 3 (Sun) | 7 | **Human-in-the-Loop** — risk-tagged tools, approval queue | ships via git pull |
| 3 (Sun) | 8 | **MCP + Capstone** — build a server, ship the four-pillar app | ships via git pull |

## Getting updates

```bash
git pull
```

Before you edit a lab, copy it (`cp labs/lab_2.py my_lab_2.py`) — editing `labs/*.py` in
place causes a merge conflict on the next pull. Your `.env` is git-ignored; pulls never
touch your key.

## Stuck?

The [FAQ](./labs/FAQ.md) covers the usual suspects. In class: ask in the cohort room, or
flag an instructor.
