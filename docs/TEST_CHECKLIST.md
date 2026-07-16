# Twhyne test & verification

Two layers: what a machine checks automatically, and what only a human can
judge (answer quality, real speed, the UI). Do the machine layer first — it's
one command and a second — then the manual lap in the running app.

## 1. Machine-testable (no Docker, no models, no network) — ~2 seconds

```
cd backend
python3 verify.py
```

Expect: **7/7 checks passed**. This covers the evidence-broker freeze-layer
(21 tests), math routing, the arithmetic-conservation guard (the "apple"
failure), the 36-snippet code library, KB name matching, and the SSRF
destination validator. Exit code is non-zero on any failure, so it's also
the CI gate.

Individual suites if you want detail:
```
python3 tests/test_evidence.py     # 21 evidence tests
python3 tests/test_math_node.py    # math routing / LaTeX
```

## 2. In-app lap (needs the launcher + a pulled image) — ~10 minutes

Restart the launcher first. Confirm two things before testing:
- the log says **"Downloaded newer image"** (not "up to date"), and
- the app header shows a **build id** (e.g. `build b3744d6…`).

If either is missing you're on an old image; wait a few minutes and restart.

Each row maps to a specific fix. Anything that fails: note the build id and
the exact text, that's a fast trace.

| Ask this | Expected |
|---|---|
| `What is 4,096 divided by 16?` | Typeset **256**, COMPUTED chip |
| `Solve the quadratic equation x² + 5x + 6 = 0` | Typeset **x = −3, −2** |
| `If sally has 2 apples and johnny has 3 but they split it 7 ways, what do they do?` | **"Arithmetic conflict detected… answer was withheld"** — never invents 7 apples |
| `Write a function to reverse a linked list` | Instant, EXECUTED (library hit — no minute-long wait) |
| `write me a function to do a knn` | Verifies for real (sklearn is in the image) — not a ModuleNotFound draft |
| `Plan a trip to Dubai` | Itinerary **ends with an "unverified plan" boundary note** |
| Attach a PDF, ask "key points of the attached document" | Cited answer from the PDF (📎 "indexed N sections" first) |
| Create a KB, then `tell me about <its name>` | Cited overview; partial names work ("twhyne" finds "Twhyne Docs") |
| Open a chat, close the browser, reopen | Chat still in the 💬 panel (kernel-stored, survives browser change) |
| Delete a knowledge base | Works (CORS fix); errors state a real reason |
| `set a timer for 30 seconds` then wait | Countdown chip, then an "elapsed" message ~5s after firing |
| Ask two questions back-to-back (a code one, then a math one) | Math answer lands while the code one is still thinking |
| Ctrl+C in the launcher window | Actually stops the app |

## 3. The one measurement I need back

In the launcher window, after any code or chat question, find the line:
```
Language generation: N tokens in Ss (X tok/s)
```
- **4–8 tok/s** → the mlock fix worked, speed recovered.
- **~1 tok/s** → it didn't; mlock wasn't the whole story and we keep digging.

Send that number. It's the only open measurement from this session that
needs real hardware.

## What is NOT testable yet (and shouldn't be faked)

- **Live web verification** (the Dubai plan checking the *actual* Visit Dubai
  site). The networked gateway/worker/signer isn't built — only its tested
  offline logic is. Until it exists, plans are honestly labeled UNVERIFIED.
- **GPU speed** (the `:gpu` image needs an NVIDIA card to validate — see
  `docs/GPU_VALIDATION.md`).
- **High-assurance security claims** — gated on threat modeling, pen-test,
  and independent review, per the roadmap.
