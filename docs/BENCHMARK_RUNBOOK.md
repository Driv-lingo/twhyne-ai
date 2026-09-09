# Benchmark runbook — A/B/C/D on your own machine (Windows / PowerShell)

**No new model.** The experiment isolates *architecture*, so all four
conditions run on the **same** model files you already have
(`mistral-7b-instruct-q4.gguf`, `qwen2.5-coder-7b-instruct-q4.gguf`) on the
same hardware. What changes is the **Docker image** (new code) and the
**benchmark scripts** you run on the host against it.

## 0. What you need

| Thing | Where | Why |
|---|---|---|
| Docker Desktop, running | already installed | runs the Twhyne image |
| `twhyne/twhyne:cpu` image built from `pre-prod` ≥ `6255dbc` | the launcher pulls it | contains the cognition layer + `/query/plain` + traces |
| The repo's `benchmarks/` folder from `pre-prod` | `git pull` (or download the branch ZIP) | `run_benchmark.py`, `generate_workloads.py`, `report.py`, `workloads.json` |
| Python 3 on the host | python.org | the scripts use only the standard library |

## 1. Start the new image

```powershell
cd C:\path\to\twhyne-ai
git pull origin pre-prod          # brings benchmarks\ and docs\ up to date
.\launch-twhyne.bat               # pulls the newest image and starts it
```
Wait for "Twhyne AI is running", then **verify you are on the new build**:
```powershell
curl http://localhost:5002/version
```
It must print a build starting with `6255dbc` (or later). If it shows an
older hash, the image has not been pulled — run `docker pull twhyne/twhyne:cpu`
and relaunch. Do not run the benchmark on an older build.

## 2. One-time: make sure the state directory is clean

Condition D must mature **from zero**. The persistent state lives in the
mounted volume:
```powershell
Remove-Item "$env:USERPROFILE\.twhyne\rag\competencies.json" -ErrorAction SilentlyContinue
Remove-Item "$env:USERPROFILE\.twhyne\rag\task_traces.jsonl"  -ErrorAction SilentlyContinue
```
(`wda.json` / `beliefs.json` may stay; they are empty on a fresh install.)

## 3. Run the four conditions

Time is the constraint: on a 6-core CPU at ~1.5–2 tok/s, every task that
reaches the model costs 1–3 minutes. Run the **focused slice first** — it is
the C-vs-D question plus the safety check — then the full set overnight.

```powershell
cd benchmarks

# ---- focused slice: 80 deterministic + 30 OOD near-matches (110 tasks) ----
python run_benchmark.py --mode plain      --tasks workloads.json --categories deterministic,ood --out results-A.json
python run_benchmark.py --mode current    --tasks workloads.json --categories deterministic,ood --out results-B.json
python run_benchmark.py --mode structured --tasks workloads.json --categories deterministic,ood --out results-C.json
Remove-Item "$env:USERPROFILE\.twhyne\rag\competencies.json" -ErrorAction SilentlyContinue
python run_benchmark.py --mode full       --tasks workloads.json --categories deterministic,ood --out results-D.json

python report.py --run A=results-A.json --run B=results-B.json --run C=results-C.json --run D=results-D.json
```
Then the full 210-task set (drop `--categories`), same order, with the same
`Remove-Item` before D.

Notes
- Each `--mode` is sent per request; you do **not** restart the container
  between conditions.
- `--categories` in this runner exits non-zero if any task fails; that is
  fine here — read the `results-*.json`, not the exit code.
- Expect condition **D** to get *faster as it goes* on the deterministic
  family (that is the hypothesis); expect the **OOD** family to stay at
  K-level in every condition (that is the safety property). If either does
  not happen, that is a finding, not a mistake in your run.

## 4. What to send back

The four `results-*.json` files (and `report.py`'s printed table). Every
number the write-up will use comes from those files: accuracy, latency,
tokens, model calls, CPU, K/R/S mix, NDR(n), CCR, FP activation, OOD recall,
break-even n\*. Nothing is estimated.

## 5. Known confounds to read the results with

- **SymPy already short-circuits pure arithmetic** ("What is 15% of 240?")
  in B, C and D via the existing math node. Families where C and D can
  differ are the ones SymPy cannot parse: unit conversions, worded
  discounts, schedules, compositions. The report separates families for
  exactly this reason.
- Condition A answers everything with the bare model, including questions
  the other conditions never send to a model; its accuracy on arithmetic
  is a model property, not an architecture property.
- TTFT and energy print `n/a` — unmeasurable on this build, not omitted.
