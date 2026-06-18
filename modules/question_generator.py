
from __future__ import annotations

import os
import random
from typing import Dict, List, Optional

import pandas as pd

from .data_loader import filter_bank, normalize_role


SYSTEM_PROMPT = """You are an interview coach. Generate concise, role-specific interview questions for the candidate.
Return JSON only with keys: questions (array of objects), where each object has:
question, category, difficulty, why, ideal_points.
Keep questions practical and appropriate for an SDE internship interview."""

def _try_llm_generate(role: str, count: int, difficulty: str, resume_text: str, api_provider: str, api_key: str) -> Optional[List[Dict]]:
    if not api_key:
        return None

    prompt = f"""
Role: {role}
Count: {count}
Difficulty: {difficulty}
Resume context: {resume_text[:2500] if resume_text else "N/A"}

Generate interview questions.
"""
    try:
        if api_provider.lower() == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            text = resp.output_text
        else:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
            resp = model.generate_content(SYSTEM_PROMPT + "\n\n" + prompt)
            text = resp.text

        import json
        # Best-effort extraction
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
        data = json.loads(text)
        qs = data.get("questions", [])
        cleaned = []
        for q in qs[:count]:
            if isinstance(q, dict) and q.get("question"):
                cleaned.append({
                    "question": str(q.get("question")).strip(),
                    "category": str(q.get("category", "General")).strip(),
                    "difficulty": str(q.get("difficulty", difficulty)).strip().lower(),
                    "why": str(q.get("why", "Role-relevant interview practice")).strip(),
                    "ideal_points": str(q.get("ideal_points", "")).strip(),
                })
        return cleaned or None
    except Exception:
        return None


def _fallback_generate(bank: pd.DataFrame, role: str, count: int, difficulty: str) -> List[Dict]:
    subset = filter_bank(bank, role, difficulty)
    if subset.empty:
        subset = bank.copy()

    # Prefer varied questions
    subset = subset.sample(frac=1.0, random_state=random.randint(1, 99999)).reset_index(drop=True)
    chosen = subset.head(count)

    out = []
    for _, row in chosen.iterrows():
        out.append({
            "question": row["question"],
            "category": row.get("category", "General") or "General",
            "difficulty": row.get("difficulty", difficulty) or difficulty,
            "why": f"Matches the target role: {role.title()}",
            "ideal_points": row.get("ideal_points", "") or "Answer with concise, structured points.",
        })

    # If we still need more, create role-specific templates
    templates = [
        "Tell me about a project where you used {skill}.",
        "How would you design a {system} for a production app?",
        "Explain a time you debugged a difficult issue.",
        "What trade-offs would you consider between {a} and {b}?",
        "How do you ensure code quality in a team project?",
    ]
    extras = [
        {"skill":"React", "system":"simple interview practice app", "a":"SQL", "b":"NoSQL"},
        {"skill":"Python", "system":"mock interview platform", "a":"REST", "b":"GraphQL"},
        {"skill":"APIs", "system":"question evaluation service", "a":"monolith", "b":"microservices"},
    ]
    i = 0
    while len(out) < count:
        t = templates[i % len(templates)]
        extra = extras[i % len(extras)]
        q = t.format(**extra)
        out.append({
            "question": q,
            "category": "Behavioral",
            "difficulty": difficulty if difficulty != "mixed" else "medium",
            "why": f"Useful for {role.title()} interviews",
            "ideal_points": "Use STAR structure, explain impact, and mention trade-offs.",
        })
        i += 1
    return out[:count]


def generate_questions(
    bank: pd.DataFrame,
    role: str,
    count: int = 7,
    difficulty: str = "mixed",
    resume_text: str = "",
    use_llm: bool = True,
    api_provider: str = "Gemini",
    api_key: str = "",
) -> List[Dict]:
    role = normalize_role(role)

    if use_llm and api_key:
        llm_questions = _try_llm_generate(role, count, difficulty, resume_text, api_provider, api_key)
        if llm_questions:
            return llm_questions

    return _fallback_generate(bank, role, count, difficulty)
