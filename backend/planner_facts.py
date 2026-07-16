"""Seeded, dated venue-status facts for the planner (offline, pre-web.fetch).

A fully-local model cannot know a venue closed since its training cutoff.
This is NOT live verification — it is a small hand-curated list of
well-known closures/changes, each stamped with the date the fact was
recorded and its source, so the planner can flag a stale recommendation
instead of presenting it as fact. Entries expire (a closure that has
since reopened must be removed); every flag shown to the user carries the
"seeded, recorded <date>" caveat so it is never mistaken for a live check.

Extend this list as pilots surface stale recommendations. When the
Evidence Broker lands, live checks supersede these seeds for any venue
they cover.
"""

# name-matched substrings (lowercased) -> status note.
# Keep entries specific enough not to false-positive on unrelated text.
SEEDED_VENUE_STATUS = [
    {
        "match": ["burj al arab"],
        "note": "Burj Al Arab is under an ~18-month restoration; reopening "
                "reported for around October 2027.",
        "recorded": "2026-07",
        "source": "visitdubai.com",
    },
    {
        "match": ["bollywood park"],
        "note": "Bollywood Parks Dubai closed permanently in 2023 and is no "
                "longer part of Dubai Parks and Resorts.",
        "recorded": "2026-07",
        "source": "dubaiparksandresorts.com",
    },
    {
        "match": ["dubai museum", "al fahidi fort"],
        "note": "The Dubai Museum in Al Fahidi Fort is closed for renovation; "
                "the fort can currently only be viewed from outside.",
        "recorded": "2026-07",
        "source": "visitdubai.com",
    },
]


def stale_venue_flags(text):
    """Return [(matched_phrase, entry)] for every seeded venue named in text.
    Deterministic; no network."""
    low = (text or "").lower()
    hits = []
    for entry in SEEDED_VENUE_STATUS:
        for phrase in entry["match"]:
            if phrase in low:
                hits.append((phrase, entry))
                break
    return hits


def stale_venue_note(text):
    """A user-facing note listing seeded stale venues in `text`, or '' if
    none. Every line carries its recorded date + source so it is never
    read as a live verification."""
    hits = stale_venue_flags(text)
    if not hits:
        return ""
    lines = ["\n\n⚠ **Known stale recommendations** (checked against Twhyne's "
             "seeded local list — NOT a live source):"]
    for _phrase, e in hits:
        lines.append(f"- {e['note']} _(recorded {e['recorded']}, "
                     f"source: {e['source']})_")
    lines.append("These are hand-curated facts that may themselves be out of "
                 "date; confirm before booking.")
    return "\n".join(lines)
