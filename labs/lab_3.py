"""Lab 3 — Strong RAG, Proven (interactive CLI tutor)

Modern AI Pro · Level 2 · AI Practitioner · Day 2

    python labs/lab_3.py

You build retrieval-augmented generation over Meridian Corp's policy corpus —
and you PROVE it's good. Chunking, embeddings, keyword search, hybrid fusion,
citations, and the practitioner move almost everyone skips: a golden set and
an LLM judge, so "strong" is a number on a scorecard, not a feeling.

The corpus hides real traps: multi-hop facts and a superseded policy version.
Naive retrieval falls into them; you'll watch it happen, then fix it.

Enter runs each stage · s skips · q quits. Piped input auto-runs (CI-safe).
"""

import json
import math
import re
from pathlib import Path

from _kit import Stage, banner, chat, client, meter, say, stages

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"

# The through-line fixture: question → what a correct answer must contain.
GOLDEN = [
    ("Who has to approve a $900 flight before booking?",
     "The traveler's VP, in writing (current v4 policy)."),
    ("How fast must a security incident be reported, and from what moment?",
     "Within 1 hour of DISCOVERY (not confirmation), to secops@."),
    ("How long are logs with personal data kept?",
     "90 days, then purged or anonymized."),
    ("Can a contractor get production access for a day?",
     "No — contractors are tier-C: no production access at all."),
    ("I want to buy a $30k analytics SaaS — what does approval require?",
     "Three quotes + a purchase order, PLUS a Vendor Risk security review (software always needs one)."),
    ("When is a postmortem due after a SEV-1?",
     "Within 5 business days, blameless, action items tracked by the reliability guild."),
]

# ── the store (built once, in memory) ───────────────────────────────────────

STORE: list[dict] = []  # {doc, text, vec}


def tokenize(s: str) -> list[str]:
    return re.findall(r"[a-z0-9$%-]+", s.lower())


def chunk(text: str, target_words: int = 90) -> list[str]:
    """Paragraph-aware chunking: split on blank lines, then pack to ~target."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    # headers travel with their body so a chunk carries its own context
    out, buf, n = [], [], 0
    for p in paras:
        w = len(p.split())
        if n + w > target_words and buf:
            out.append("\n".join(buf))
            buf, n = [], 0
        buf.append(p)
        n += w
    if buf:
        out.append("\n".join(buf))
    return out


def embed(cli, texts: list[str]) -> list[list[float]]:
    resp = cli.embeddings.create(model="mai-embed", input=texts)
    meter.calls += 1
    return [d.embedding for d in resp.data]


def cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def bm25_scores(query: str) -> list[float]:
    """BM25 in 20 lines — the 50-year-old keyword algorithm that still earns
    its keep. No library, so you can read every term."""
    k1, b = 1.5, 0.75
    docs = [tokenize(c["text"]) for c in STORE]
    avgdl = sum(len(d) for d in docs) / max(len(docs), 1)
    n = len(docs)
    scores = [0.0] * n
    for term in set(tokenize(query)):
        df = sum(1 for d in docs if term in d)
        if df == 0:
            continue
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for i, d in enumerate(docs):
            tf = d.count(term)
            scores[i] += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(d) / avgdl))
    return scores


def rrf(rank_lists: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal-rank fusion: agreement between searchers beats either score."""
    points: dict[int, float] = {}
    for ranks in rank_lists:
        for pos, idx in enumerate(ranks):
            points[idx] = points.get(idx, 0.0) + 1.0 / (k + pos + 1)
    return sorted(points, key=points.get, reverse=True)


def top(scores: list[float]) -> list[int]:
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)


def retrieve(cli, query: str, k: int = 3, hybrid: bool = True) -> list[dict]:
    qv = embed(cli, [query])[0]
    sem = top([cosine(qv, c["vec"]) for c in STORE])
    if not hybrid:
        return [STORE[i] for i in sem[:k]]
    lex = top(bm25_scores(query))
    return [STORE[i] for i in rrf([sem, lex])[:k]]


def answer(cli, query: str, chunks: list[dict], label: str = "rag") -> str:
    ctx = "\n\n".join(f"[{i+1}] ({c['doc']})\n{c['text']}" for i, c in enumerate(chunks))
    return chat(cli, [
        {"role": "system", "content":
            "Answer ONLY from the sources below. Cite like [1][2] after each claim. "
            "Prefer the CURRENT version when sources conflict; superseded versions say so. "
            "If the sources don't contain the answer, say exactly that.\n\n" + ctx},
        {"role": "user", "content": query},
    ], label=label, max_tokens=220)


# ── Stage 1 · chunk + embed the corpus ──────────────────────────────────────

def stage_build(cli):
    say(f"Corpus: {CORPUS_DIR.name}/ — Meridian Corp's policy binder.\n")
    for f in sorted(CORPUS_DIR.glob("*.md")):
        for c in chunk(f.read_text()):
            STORE.append({"doc": f.name, "text": c, "vec": None})
    say(f"  {len(list(CORPUS_DIR.glob('*.md')))} docs → {len(STORE)} chunks "
        f"(~90 words each, headers kept with their bodies)")
    vecs = embed(cli, [c["text"] for c in STORE])
    for c, v in zip(STORE, vecs):
        c["vec"] = v
    say(f"  embedded all {len(STORE)} chunks in one metered call — dim {len(vecs[0])}\n")
    say("Chunking IS a retrieval decision: too big and answers hide inside noise;")
    say("too small and multi-sentence facts get cut in half. ~90 words is a start,")
    say("not a law — real systems tune this against the golden set you build in stage 4.")


# ── Stage 2 · semantic vs keyword vs hybrid ─────────────────────────────────

def stage_search(cli):
    q = "Who approves an $800+ flight?"
    say(f"One query, three searchers — [bold]{q}[/bold]\n")
    qv = embed(cli, [q])[0]
    sem = top([cosine(qv, c["vec"]) for c in STORE])[:3]
    lex = top(bm25_scores(q))[:3]
    fused = rrf([top([cosine(qv, c["vec"]) for c in STORE]), top(bm25_scores(q))])[:3]
    for name, idxs in (("semantic (embeddings)", sem), ("keyword (BM25)", lex), ("hybrid (RRF)", fused)):
        say(f"  [yellow]{name}:[/yellow]")
        for i in idxs:
            say(f"    · {STORE[i]['doc']} — [dim]{STORE[i]['text'][:70]}…[/dim]")
    say("\nSemantic search understands MEANING but shrugs at exact strings ($800,")
    say("SEV-1, FIN-204); keyword search nails strings but not paraphrase. Hybrid")
    say("fusion (RRF — read it above, it's 8 lines) takes agreement as evidence.")
    say("Notice the superseded 2024 policy lurking in the results — stage 5's trap.")


# ── Stage 3 · grounded answers with citations ───────────────────────────────

def stage_grounded(cli):
    for q in ("How long do we keep logs that contain personal data?",
              "What's the meal cap on a trip to our Berlin office?"):
        chunks = retrieve(cli, q)
        out = answer(cli, q, chunks)
        say(f"  [bold]{q}[/bold]")
        say(f"  {out}")
        say(f"  [dim]sources: {', '.join(c['doc'] for c in chunks)}[/dim]\n")
    say("Citations aren't decoration — they are the audit trail that lets a reader")
    say("(or a judge, next stage) check every claim against its source.")


# ── Stage 4 · the golden set + the judge ────────────────────────────────────

def run_suite(cli, hybrid: bool) -> tuple[int, list[str]]:
    passed, notes = 0, []
    for q, expected in GOLDEN:
        out = answer(cli, q, retrieve(cli, q, hybrid=hybrid),
                     label="suite-hybrid" if hybrid else "suite-naive")
        verdict = chat(cli, [
            {"role": "system", "content":
                'You are a strict grader. Given QUESTION, EXPECTED facts, and ANSWER, '
                'respond ONLY JSON: {"pass": true|false, "why": str}. '
                "Pass only if the answer contains the expected facts and no contradiction."},
            {"role": "user", "content":
                f"QUESTION: {q}\nEXPECTED: {expected}\nANSWER: {out}"},
        ], label="judge", max_tokens=100, response_format={"type": "json_object"})
        try:
            v = json.loads(verdict.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
        except json.JSONDecodeError:
            v = {"pass": False, "why": "judge returned non-JSON"}
        ok = bool(v.get("pass"))
        passed += ok
        notes.append(f"  {'[green]PASS[/green]' if ok else '[red]FAIL[/red]'} {q}"
                     + ("" if ok else f"\n        [dim]{v.get('why','')}[/dim]"))
    return passed, notes


HYBRID_SCORE: list[int] = []  # stage 4 stores its result so stage 5 reuses it


def stage_golden(cli):
    say("A RAG system without an eval set is a demo. Here is the whole discipline")
    say(f"in miniature — {len(GOLDEN)} golden cases, each 'question → facts a correct")
    say("answer must contain', graded by an LLM judge:\n")
    passed, notes = run_suite(cli, hybrid=True)
    HYBRID_SCORE.append(passed)
    for n in notes:
        say(n)
    say(f"\n  [bold]scorecard: {passed}/{len(GOLDEN)}[/bold] — remember this number.")
    say("\nEvery change you ever make to this system — new chunking, new model, new")
    say("prompt — reruns this suite. Beat the number or the change doesn't ship.")


# ── Stage 5 · prove hybrid earns its keep ───────────────────────────────────

def stage_ablation(cli):
    say("Claim from stage 2: hybrid beats semantic-only. Don't believe it — measure it.\n")
    naive, _ = run_suite(cli, hybrid=False)
    hybrid = HYBRID_SCORE[0] if HYBRID_SCORE else run_suite(cli, hybrid=True)[0]
    say(f"  semantic-only : {naive}/{len(GOLDEN)}")
    say(f"  hybrid (RRF)  : {hybrid}/{len(GOLDEN)}\n")
    if hybrid >= naive:
        say("Hybrid held or won — on a 6-case set the gap can be small; on a real")
        say("corpus with part numbers, dollar figures and acronyms it is decisive.")
    else:
        say("Semantic won this run! Small sets are noisy — which is itself the")
        say("lesson: eval sets need enough cases to make a verdict stick.")
    say("This stage is an ABLATION — the practitioner habit of earning every")
    say("component with a before/after on the same golden set. Also check: did any")
    say("answer cite the superseded 2024 travel policy? The judge would have caught it.")


if __name__ == "__main__":
    banner("Level 2 · AI Practitioner · Day 2", "Lab 3 · Strong RAG, Proven")
    cli = client()
    stages(cli, [
        Stage("Build the store — chunk + embed",
              why="A model can't answer from documents it never sees, and you "
                  "can't paste a whole binder into every prompt (Lab 1: context "
                  "is the cost driver). So RAG splits the problem: store the "
                  "corpus as SEARCHABLE pieces now, retrieve only the relevant "
                  "few at question time. First decision: what IS a piece? "
                  "Chunk size trades recall against noise.",
              fn=stage_build,
              logic="Each chunk became a vector — a point in meaning-space where "
                    "nearby means similar. Note what was decided FOR you by "
                    "chunking at ~90 words with headers attached: a fact split "
                    "across two chunks is now hard to retrieve whole. Chunking "
                    "is a retrieval decision, and stage 4 gives you the "
                    "instrument to tune it against evidence."),
        Stage("Three searchers — semantic · keyword · hybrid",
              why="Two search paradigms, two failure modes — embeddings "
                  "understand paraphrase but blur exact strings ($800, SEV-1); "
                  "keyword search (BM25, 20 readable lines above) nails strings "
                  "but not meaning. If the failure modes are DIFFERENT, "
                  "combining the two searchers should beat either. RRF tests "
                  "that: it scores agreement between rank lists.",
              fn=stage_search,
              logic="The fused list kept the right doc at top while each single "
                    "searcher wobbled — agreement between independent rankers "
                    "is evidence neither provides alone. That's the same logic "
                    "as asking two doctors: correlated errors are rare. Also "
                    "spotted: the superseded 2024 policy ranks well too — "
                    "retrieval alone can't know it's stale. Stage 3's prompt "
                    "must handle that."),
        Stage("Grounded answers with citations",
              why="Retrieval found candidates; now generation must answer FROM "
                  "them and only them — plus survive two traps we planted: a "
                  "conflicting superseded version (recency) and a question the "
                  "corpus can't answer (where honesty beats helpfulness). "
                  "Citations make every claim auditable back to its source.",
              fn=stage_grounded,
              logic="The system prompt did three jobs: restrict to sources, "
                    "prefer current over superseded, admit gaps. A citation "
                    "isn't decoration — it converts 'trust me' into 'check me', "
                    "which is what lets the next stage grade answers "
                    "mechanically. Ungrounded fluency is the failure mode; "
                    "grounded refusal is a SUCCESS."),
        Stage("The golden set + the LLM judge",
              why="'It seems good' doesn't survive contact with change — every "
                  "tweak to chunking, model or prompt needs re-checking, and "
                  "humans won't re-read 6 answers per tweak (nor 600 in a real "
                  "system). Fix: freeze question→expected-facts pairs and let a "
                  "second model GRADE against them — Lab 1's structured-output "
                  "move, now grading instead of extracting.",
              fn=stage_golden,
              logic="You now hold a NUMBER instead of a feeling — and a FAIL "
                    "with the judge's reason attached, which is a repair map: "
                    "was it retrieval (wrong chunks) or generation (right "
                    "chunks, wrong words)? The discipline: every future change "
                    "reruns this suite; beat the number or don't ship. That "
                    "loop — not any single technique — is what 'strong RAG' "
                    "means."),
        Stage("The ablation — prove hybrid earns its keep",
              why="Stage 2 argued hybrid should win; arguments aren't evidence. "
                  "An ablation removes exactly one component (BM25 fusion) and "
                  "reruns the SAME golden set — any score change is attributable "
                  "to that component alone. This is how practitioners earn "
                  "every box in their architecture diagram.",
              fn=stage_ablation,
              logic="Whatever the margin, you now know hybrid's contribution as "
                    "a measurement, not a belief — and you felt the caveat: on "
                    "6 cases one flip moves 17 points, so verdicts need enough "
                    "cases to stick. Habit to keep: no component ships on "
                    "reputation; every one pays rent on the golden set."),
    ])
    meter.show()
