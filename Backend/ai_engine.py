"""The 'AI' matching engine.

It's a transparent, rule-based scorer rather than a trained model -
that's a reasonable and honest choice for this project. This module
keeps the scoring weights in one place and returns a breakdown so the
UI can explain *why* a score looks the way it does, not just the
number itself.
"""

WEIGHTS = {
    "cgpa": 40,
    "skills": 20,   # per matching required skill
    "location": 20,
    "department": 20,
}


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _split_terms(text):
    if not text:
        return []
    return [term.strip().lower() for term in text.split(",") if term.strip()]


def calculate_match(student, internship):
    """Return a dict with the total score (0-100, clamped) and a
    breakdown of which criteria matched, for a student/internship pair.
    """
    reasons = []
    score = 0

    student_cgpa = _to_float(student["cgpa"])
    required_cgpa = _to_float(internship["minimum_cgpa"])
    cgpa_ok = student_cgpa >= required_cgpa
    if cgpa_ok:
        score += WEIGHTS["cgpa"]
        reasons.append(f"CGPA {student_cgpa:.2f} meets the {required_cgpa:.2f} requirement")
    else:
        reasons.append(f"CGPA {student_cgpa:.2f} is below the {required_cgpa:.2f} requirement")

    student_skills = _split_terms(student["skills"])
    required_skills = _split_terms(internship["required_skills"])
    matched_skills = [s for s in required_skills if s in student_skills]
    if required_skills:
        score += WEIGHTS["skills"] * len(matched_skills)
        if matched_skills:
            reasons.append(f"Matches {len(matched_skills)}/{len(required_skills)} required skills")
        else:
            reasons.append("No required skills matched")

    location_match = (student["preferred_location"] or "").strip().lower() == (
        internship["location"] or ""
    ).strip().lower()
    if location_match:
        score += WEIGHTS["location"]
        reasons.append("Preferred location matches")

    department_match = (student["department"] or "").strip().lower() in (
        internship["role"] or ""
    ).strip().lower()
    if department_match:
        score += WEIGHTS["department"]
        reasons.append("Department aligns with the role")

    score = max(0, min(100, score))

    return {
        "score": score,
        "cgpa_ok": cgpa_ok,
        "matched_skills": matched_skills,
        "required_skills": required_skills,
        "location_match": location_match,
        "department_match": department_match,
        "reasons": reasons,
    }
