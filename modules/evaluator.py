
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

import pandas as pd


def _safe_split_points(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"[.;\n]+", text)
    return [p.strip().lower() for p in parts if p.strip()]


def _heuristic_evaluate(question: Dict, answer: str, role: str, resume_text: str = "") -> Dict:
    answer = (answer or "").strip()
    q_text = question.get("question", "")
    ideal = question.get("ideal_points", "")
    points = _safe_split_points(ideal)

    score = 0
    strengths = []
    improvements = []

    # Length and structure
    word_count = len(answer.split())
    if word_count >= 80:
        score += 20
        strengths.append("Detailed answer")
    elif word_count >= 40:
        score += 15
        strengths.append("Reasonable depth")
    elif word_count >= 15:
        score += 8
    else:
        improvements.append("Add more detail")

    # Basic structure markers
    if any(marker in answer.lower() for marker in ["first", "second", "finally", "for example", "because"]):
        score += 12
        strengths.append("Structured explanation")
    else:
        improvements.append("Use a clearer structure")

    # Match to expected points
    matched = 0
    for p in points:
        if p and any(token in answer.lower() for token in p.split()[:4]):
            matched += 1
    if points:
        pct = matched / max(1, min(len(points), 5))
        score += int(35 * pct)
        if pct > 0.6:
            strengths.append("Covers key concepts")
        elif pct < 0.3:
            improvements.append("Mention core technical terms")

    # Confidence and clarity
    if any(word in answer.lower() for word in ["i built", "i designed", "i optimized", "i improved"]):
        score += 10
        strengths.append("Shows ownership")
    if any(word in answer.lower() for word in ["maybe", "not sure", "guess"]):
        score -= 5
        improvements.append("Sound more confident")

    # Resume relevance bonus
    if resume_text and any(skill in answer.lower() for skill in ["react", "python", "sql", "node", "mongodb", "streamlit"]):
        score += 5

    score = max(0, min(100, score))

    if score >= 85:
        feedback = "Excellent answer. You explained the concept clearly and covered the expected points well."
    elif score >= 70:
        feedback = "Good answer. It is solid, but you can make it sharper and more specific."
    elif score >= 50:
        feedback = "Fair answer. It has the right direction, but it needs more structure and technical depth."
    else:
        feedback = "The answer is too brief or incomplete. Add structure, examples, and core concepts."

    if not strengths:
        strengths = ["Basic attempt"]
    if not improvements:
        improvements = ["Add one practical example"]

    rubric = {
        "length": word_count,
        "matched_ideal_points": matched,
        "expected_points": points[:5],
        "role": role,
    }
    return {
        "score": score,
        "feedback": feedback,
        "strengths": strengths[:3],
        "improvements": improvements[:3],
        "rubric": rubric,
    }


def _try_llm_evaluate(question: Dict, answer: str, role: str, resume_text: str, api_provider: str, api_key: str) -> Optional[Dict]:
    if not api_key:
        return None

    prompt = f"""
Role: {role}
Question: {question.get('question','')}
Ideal points: {question.get('ideal_points','')}
Candidate answer: {answer}
Resume context: {resume_text[:2000] if resume_text else 'N/A'}

Return JSON only with keys:
score (0-100), feedback, strengths (array), improvements (array), rubric (object).
Keep feedback concise and actionable.
"""
    try:
        if api_provider.lower() == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                input=[
                    {"role": "system", "content": "You are an interview evaluator. Return only JSON."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = resp.output_text
        else:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
            resp = model.generate_content("Return JSON only.\n\n" + prompt)
            text = resp.text

        import json
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
        data = json.loads(text)
        data.setdefault("score", 0)
        data.setdefault("feedback", "")
        data.setdefault("strengths", [])
        data.setdefault("improvements", [])
        data.setdefault("rubric", {})
        return data
    except Exception:
        return None


def evaluate_answer(
    question: Dict,
    answer: str,
    role: str,
    use_llm: bool = True,
    api_provider: str = "Gemini",
    api_key: str = "",
    resume_text: str = "",
) -> Dict:
    if use_llm and api_key:
        result = _try_llm_evaluate(question, answer, role, resume_text, api_provider, api_key)
        if result:
            return result

    return _heuristic_evaluate(question, answer, role, resume_text)
