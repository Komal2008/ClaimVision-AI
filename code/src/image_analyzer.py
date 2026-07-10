import os
import json
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")


def _estimate_repair_cost(claim_object, severity):
    severity = str(severity or "unknown").lower()
    object_type = str(claim_object or "unknown").lower()
    ranges = {
        "car": {
            "high": "INR 15,000-40,000",
            "medium": "INR 7,500-18,000",
            "low": "INR 5,000-12,000",
            "none": "INR 3,000-8,000",
            "unknown": "INR 3,000-8,000",
        },
        "laptop": {
            "high": "INR 20,000-50,000",
            "medium": "INR 8,000-18,000",
            "low": "INR 2,000-6,000",
            "none": "INR 1,000-3,000",
            "unknown": "INR 1,000-3,000",
        },
        "package": {
            "high": "INR 3,000-8,000",
            "medium": "INR 1,200-3,000",
            "low": "INR 500-1,400",
            "none": "INR 250-700",
            "unknown": "INR 250-700",
        },
    }
    return ranges.get(object_type, {}).get(severity, "INR 500-7,500")


def _confidence_score(result):
    severity = str(result.get("severity") or "unknown").lower()
    quality_flags = result.get("quality_flags") or []
    if isinstance(quality_flags, str):
        quality_flags = [quality_flags]

    score = 55
    score += 20 if result.get("damage_visible", False) else -18
    score += 10 if result.get("valid_image", False) else -22

    if severity == "high":
        score += 8
    elif severity == "medium":
        score += 6
    elif severity == "low":
        score += 3
    elif severity in {"none", "unknown"}:
        score -= 6

    score -= min(len(quality_flags) * 6, 18)
    return max(10, min(98, int(round(score))))


def _repair_guidance(claim_object, result):
    object_type = str(result.get("object_type") or claim_object or "item").lower()
    part = str(result.get("object_part") or "").replace("_", " ").strip().lower()
    issue = str(result.get("issue_type") or "").replace("_", " ").strip().lower()
    severity = str(result.get("severity") or "unknown").lower()

    if not result.get("damage_visible"):
        return ["Request clearer evidence", "Perform manual inspection"]

    if object_type == "car":
        guidance = []
        if "bumper" in part:
            guidance.append(f"{part.title()} repair")
        elif part and part != "unknown":
            guidance.append(f"{part.title()} panel repair")
        else:
            guidance.append("Body panel inspection")
        if "dent" in issue or severity in {"medium", "high"}:
            guidance.append("Dent removal")
        if issue in {"scratch", "dent"} or severity in {"low", "medium"}:
            guidance.append("Paint correction")
        if severity == "high":
            guidance.append("Replacement assessment")
        return list(dict.fromkeys(guidance))

    if object_type == "laptop":
        guidance = ["Hardware diagnostics", "Exterior casing repair"]
        if severity in {"medium", "high"}:
            guidance.append("Screen or component replacement assessment")
        return guidance

    if object_type == "package":
        guidance = ["Packaging inspection", "Contents damage assessment"]
        if severity in {"medium", "high"}:
            guidance.append("Replacement or refund review")
        return guidance

    return ["Damage inspection", "Repair feasibility assessment"]


def _apply_result_contract(result, claim_object):
    result = dict(result or {})
    result.setdefault("object_type", claim_object)
    result.setdefault("issue_type", "unknown")
    result.setdefault("object_part", "unknown")
    result.setdefault("damage_visible", False)
    result.setdefault("severity", "unknown")
    result.setdefault("valid_image", False)
    result.setdefault("quality_flags", [])
    result["confidence_score"] = result.get("confidence_score") or _confidence_score(
        result
    )
    fraud_risk = result.get("fraud_risk")
    if not fraud_risk or str(fraud_risk).strip().lower() == "unknown":
        fraud_risk = "Low"
    result["fraud_risk"] = fraud_risk
    result["fraud_risk_score"] = result.get("fraud_risk_score") or 24
    repair_estimate = result.get("repair_estimate")
    if not repair_estimate or str(repair_estimate).strip().lower() in {
        "none",
        "unknown",
        "--",
    }:
        repair_estimate = _repair_guidance(claim_object, result)
    result["repair_estimate"] = repair_estimate

    estimated_cost = result.get("estimated_cost")
    if not estimated_cost or str(estimated_cost).strip().lower() in {
        "none",
        "unknown",
        "--",
    }:
        estimated_cost = _estimate_repair_cost(
            result.get("object_type"), result.get("severity")
        )
    result["estimated_cost"] = estimated_cost
    result["estimated_repair_cost"] = result["estimated_cost"]
    return result


def analyze_image(image_path, claim_object):

    image = Image.open(image_path)

    prompt = f"""
You are an insurance damage reviewer.

Analyze the image carefully.

IMPORTANT:
Return ONLY valid JSON.
Do not include markdown.
Do not include explanations.

Allowed issue_type values:
dent
scratch
crack
glass_shatter
broken_part
missing_part
torn_packaging
crushed_packaging
water_damage
stain
none
unknown

Allowed severity values:
none
low
medium
high
unknown

Determine:
1. Visible damage type
2. Object part
3. Whether damage is visible
4. Whether image is valid
5. Quality problems

Return ONLY:

{{
  "object_type": "{claim_object}",
  "issue_type": "",
  "object_part": "",
  "damage_visible": true,
  "severity": "",
  "valid_image": true,
  "quality_flags": [],
  "confidence_score": 0,
  "fraud_risk": "",
  "repair_estimate": [],
  "estimated_cost": ""
}}
"""

    try:
        response = model.generate_content([prompt, image])

        cleaned = response.text.replace("```json", "").replace("```", "").strip()

        return _apply_result_contract(json.loads(cleaned), claim_object)

    except Exception as e:

        print(f"Gemini Error: {e}")

        return _apply_result_contract(
            {
                "object_type": claim_object,
                "issue_type": "unknown",
                "object_part": "unknown",
                "damage_visible": False,
                "severity": "unknown",
                "valid_image": False,
                "quality_flags": ["manual_review_required"],
            },
            claim_object,
        )
