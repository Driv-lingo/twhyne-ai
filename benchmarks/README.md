# Twhyne Benchmark Harness

This harness measures where Twhyne's **routed system** (router + specialist
nodes + deterministic tools + RAG grounding) actually matches, ties, or loses
against frontier cloud models — task by task, honestly.

The thesis we are testing is **not** "a 7B beats GPT-4 in general." It is:
> For narrow, well-defined tasks (exact math, grounded Q&A on your own
> documents, code), a routed system of small experts + tools + retrieval
> produces frontier-quality, *verifiable* answers on hardware you own.

So the scoring rewards **correctness and grounding**, not eloquence.

## What it does

1. Spins up nothing — it talks to your **already-running backend** on
   `http://localhost:5002` (start the app first).
2. Auto-creates a RAG dataset from every file in `corpus/` so the grounded
   tasks have something to retrieve from.
3. Sends each task in `tasks.json` through `/query` and scores the answer
   with a task-appropriate checker:
   - **math** — numeric exact match (SymPy path must be right, not close).
   - **grounded_qa** — must contain the supported facts, must cite the
     source, and must NOT contain a known hallucination.
   - **code** — must contain the required constructs.
   - **general** — must contain the expected key facts.
4. Optionally runs the SAME tasks against a cloud model for a side-by-side
   win/tie/loss, if you set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.
5. Prints a per-category summary and writes `results.json`.

## Usage

```bash
# 1. Start the app (models must be present in ~/.twhyne/models)
# 2. Run the harness (stdlib only, no pip installs needed):
python benchmarks/run_benchmark.py

# Compare against a cloud model:
OPENAI_API_KEY=sk-... python benchmarks/run_benchmark.py --cloud openai
ANTHROPIC_API_KEY=sk-... python benchmarks/run_benchmark.py --cloud anthropic

# Point at a non-default backend:
python benchmarks/run_benchmark.py --base-url http://localhost:5002
```

## Adding tasks

Edit `tasks.json`. Each task is one object in a category list. See the file for
the field shapes. Grounded tasks should only assert facts that are actually in
`corpus/` — that is the whole point (we cite what we retrieved, nothing else).

## Reading the results

- **Local accuracy** is the real headline: on math and grounded Q&A we expect
  to be at or near 100%, because those paths are deterministic/retrieved.
- **vs cloud** is context: on grounded Q&A about *your* corpus we should tie
  or win (the cloud model has never seen your documents); on open general
  reasoning we will lose, and that is expected and honest.
