# Language-node model comparison

**Scope:** which 7–8B instruct model should drive Twhyne's *language* node
(prose, explanations, grounded RAG answers). The code node stays on
Qwen2.5-Coder-7B; the math node is SymPy (no model). This is a **decision
aid built from published benchmarks**, not a local run — see "Measure it
yourself" at the bottom for the Twhyne-consistent way to settle it.

> Honesty note: the numbers below are approximate published figures from
> each model's release materials and common leaderboards. They are directional,
> not authoritative, and they were **not** measured on Twhyne's tasks or on
> CPU-Q4. Treat this table as "who to put in the harness," not "the verdict."

## The candidates

| | Current | Contender | Contender |
|---|---|---|---|
| Model | OpenHermes-2.5-**Mistral-7B** | **Qwen2.5-7B-Instruct** | **Llama-3.1-8B-Instruct** |
| Params | ~7.2B | ~7.6B | ~8.0B |
| Q4_K_M size | ~4.1 GB | ~4.7 GB | ~4.9 GB |
| Context | 8K (32K base) | **128K** | **128K** |
| License | **Apache-2.0** | **Apache-2.0** | Llama-3.1 Community* |
| Released | late 2023 | 2024 | mid 2024 |

\* Llama-3.1 Community License is **not** OSI-open: it carries an Acceptable
Use Policy, a "Built with Llama" attribution requirement, a clause forbidding
use of Llama outputs to improve *other* (non-Llama) models, and a >700M-MAU
trigger for a separate license. Usable commercially, but it adds
redistribution obligations that Apache-2.0 does not — and Twhyne **ships
weights to customers**, so this matters more here than for a hosted product.

## Quality (approximate, published)

| Capability | Mistral-7B (OH-2.5) | Qwen2.5-7B | Llama-3.1-8B |
|---|---|---|---|
| General knowledge (MMLU) | ~62% | **~74%** | ~68–69% |
| Reasoning (grade-school→hard) | fair | **strong** | strong |
| Instruction following | strong | strong | **strong** |
| Prose / explanation fluency | good | good | **very good** |
| Math (helps word problems) | weak | **strong** | fair |
| Multilingual | limited | **broad** | good |
| Structured output (JSON/schema) | fair | **strong** | good |
| Q4 robustness (holds up quantized) | good | **good** | good |

## What each is best at, for *this* node

- **Mistral-7B (current):** light (smallest Q4), Apache-2.0, genuinely good
  instruction-following — but it's the oldest, weakest on knowledge/math, and
  its native 8K context is the tightest for long RAG grounding.
- **Qwen2.5-7B-Instruct:** the strongest *reasoning/knowledge/structured*
  profile of the three, Apache-2.0, 128K context, excellent at exactly the
  structured/verifiable work Twhyne leans on. Slightly larger.
- **Llama-3.1-8B-Instruct:** arguably the most *natural prose*, 128K context,
  very strong instruction-following — but the license is the catch for a
  weights-shipping product, and it's the largest of the three.

## The Twhyne-specific tie-breaker (not on any leaderboard)

Twhyne already runs **Qwen2.5-Coder-7B** for the code node. Moving the
language node to **Qwen2.5-7B-Instruct** means:

1. **One model family, one tokenizer, one prompt format** across code + language
   — less prompt-shaping surface, fewer node-specific quirks.
2. A real path to **killing the model-swap latency** that dominates cold
   code↔chat transitions: same architecture family makes a single-resident or
   dual-resident strategy more coherent, and if Instruct quality is acceptable
   on code-adjacent asks you reduce how often a swap is even needed.
3. **Apache-2.0 end to end** — clean to redistribute, no per-node license
   asymmetry to track.

That systems benefit is often worth more than a couple of MMLU points.

## Recommendation

**Put Qwen2.5-7B-Instruct in the harness as the challenger to beat, with
Llama-3.1-8B as the prose-quality reference.** On paper Qwen2.5 is the best
fit for Twhyne — strongest reasoning, Apache-2.0, 128K context, family
unification with the code node. Llama-3.1's edge is prose naturalness, but its
license and size make it the weaker default *for a product that ships weights*.
Do **not** switch on this table alone — switch on measured wins over Twhyne's
own tasks.

## Measure it yourself (the verify-first way)

A leaderboard is someone else's evidence. Twhyne should decide on its own,
on-device, on its own task distribution. The harness would:

- run a fixed prompt set spanning the node's real work — explanations,
  grounded RAG answers (with the retrieval fixed so only the model varies),
  refusals, follow-ups, and a few adversarial "don't leak the KB" cases;
- score each answer on **correctness, grounding fidelity (no invented
  facts), instruction adherence, and length discipline**, plus record
  **tok/s and time-to-first-token on the target CPU**;
- emit a signed result record so the choice is auditable, exactly like every
  other Twhyne verdict.

This reuses the existing benchmark slice and CI gate. Speed and quality get
measured together — because on CPU a 3-point quality gain that halves tok/s
may be a net loss for the product, and only a local run shows that.

## Note on the compression pipeline

Distilling/compressing a large teacher into a 7B student is a sound direction
for on-prem, with one honest boundary: **you cannot losslessly fit 70B/314B
capability into 7B.** Distillation transfers a *subset* — strongest when the
student is trained on the teacher's behavior over **Twhyne's specific task
distribution** (governed answers, grounded RAG, refusals, structured output)
rather than "general capability." Two practical implications:

- The **student architecture** you compress *into* should be the one you'd
  ship anyway — an **Apache-2.0 base (Qwen2.5-7B / Mistral-7B)** keeps the
  distilled result cleanly redistributable. Distilling *from* a
  license-restricted teacher can taint the student's usage terms — check the
  teacher's license forbids using its outputs to train other models (Llama's
  does; Qwen/Apache generally don't).
- Measure the student on **the same harness above**, against the un-distilled
  7B, so "compression won" is a signed, on-device result — not a claim.
