# FAQ — the usual suspects

**`pip install -r requirements.txt` fails** — make sure the venv is active
(`source .venv/bin/activate`; the prompt shows `(.venv)`). Python 3.10+ required
(`python --version`).

**"No key found"** — you edited `.env.example` instead of `.env`, or the key line still
says `paste-your-mai_-key-here`. `cp .env.example .env`, then paste the real `mai_…` key.

**"invalid or has been rotated"** — every re-mint at
[study.modernaipro.com/practice](https://study.modernaipro.com/practice) revokes the
previous key. Use the newest one; it is shown exactly once at mint time.

**429 rate limit / quota message** — the per-key budget is generous but finite; the
message tells you where you stand. Slow a runaway loop before re-running.

**Windows** — activate with `.venv\Scripts\activate`; everything else is identical.

**`python: command not found`** — many machines (especially macOS) only have
`python3`. Use `python3 labs/lab_1.py` and `pip3 install -r requirements.txt`.

**`git pull` conflicts** — you edited a lab in place. Copy your work
(`cp labs/lab_2.py my_lab_2.py`), then `git checkout -- labs/lab_2.py` and pull again.

Anything else: the cohort room, or reply to any course email — it reaches the instructor.
