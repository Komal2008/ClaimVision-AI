ISSUE_MAP = {
    "dent": "dent",
    "dented": "dent",
    "scratch": "scratch",
    "scratched": "scratch",
    "crack": "crack",
    "cracked": "crack",
    "shatter": "glass_shatter",
    "shattered": "glass_shatter",
    "broken": "broken_part",
    "damage": "broken_part",
    "damaged": "broken_part",
    "affected": "broken_part",
    "missing": "missing_part",
    "water": "water_damage",
    "wet": "water_damage",
    "stain": "stain",
    "torn": "torn_packaging",
    "crushed": "crushed_packaging",
}

PARTS = [
    "front bumper",
    "rear bumper",
    "rear bumper",
    "rearbumper",
    "door",
    "hood",
    "windshield",
    "side mirror",
    "headlight",
    "taillight",
    "screen",
    "keyboard",
    "trackpad",
    "hinge",
    "lid",
    "corner",
    "seal",
    "label",
    "contents",
]


def extract_claim(claim_text):
    text = claim_text.lower()

    # Normalize common compound words
    text = text.replace("frontbumper", "front bumper")

    text = text.replace("rearbumper", "rear bumper")

    text = text.replace("sidemirror", "side mirror")

    issue_type = "unknown"
    object_part = "unknown"

    for key, value in ISSUE_MAP.items():
        if key in text:
            issue_type = value
            break

    for part in PARTS:
        if part in text:
            object_part = part.replace(" ", "_")
            break

    return {"issue_type": issue_type, "object_part": object_part}
