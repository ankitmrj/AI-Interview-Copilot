
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.data_loader import load_question_bank, normalize_role
from modules.question_generator import generate_questions
from modules.evaluator import evaluate_answer
from modules.resume_parser import extract_text_from_file


APP_TITLE = "AI Interview Copilot"
BASE_DIR = Path(__file__).parent
DEFAULT_DATASET = BASE_DIR / "dataset" / "interview_questions_sample.csv"


st.set_page_config(page_title=APP_TITLE, page_icon="🎯", layout="wide")


def init_state():
    if "questions" not in st.session_state:
        st.session_state.questions = []
    if "current_q_index" not in st.session_state:
        st.session_state.current_q_index = 0
    if "answers" not in st.session_state:
        st.session_state.answers = {}
    if "generated_role" not in st.session_state:
        st.session_state.generated_role = "sde intern"
    if "resume_text" not in st.session_state:
        st.session_state.resume_text = ""
    if "question_bank" not in st.session_state:
        st.session_state.question_bank = load_question_bank(DEFAULT_DATASET)


def score_summary(results):
    if not results:
        return 0, "No answers evaluated yet."
    avg = sum(r["score"] for r in results) / len(results)
    if avg >= 85:
        label = "Excellent"
    elif avg >= 70:
        label = "Good"
    elif avg >= 50:
        label = "Fair"
    else:
        label = "Needs improvement"
    return round(avg, 1), label


def render_header():
    st.title("🎯 AI Interview Copilot")
    st.caption(
        "Generate role-specific interview questions, evaluate responses, and get personalized feedback."
    )


def sidebar_controls():
    st.sidebar.header("Setup")
    role = st.sidebar.text_input("Role", value="SDE Intern", help="Examples: SDE Intern, Frontend Intern, Backend Intern")
    role_norm = normalize_role(role)

    uploaded_dataset = st.sidebar.file_uploader(
        "Optional Kaggle CSV dataset",
        type=["csv"],
        help="Upload a Kaggle interview dataset with at least a `question` column. Optional columns: role, category, difficulty, ideal_points.",
    )
    if uploaded_dataset is not None:
        try:
            st.session_state.question_bank = load_question_bank(uploaded_dataset)
            st.sidebar.success("Custom dataset loaded.")
        except Exception as e:
            st.sidebar.error(f"Could not load dataset: {e}")

    uploaded_resume = st.sidebar.file_uploader(
        "Optional resume upload",
        type=["pdf", "txt", "docx"],
        help="Use this to personalize interview questions and feedback.",
    )
    if uploaded_resume is not None:
        try:
            st.session_state.resume_text = extract_text_from_file(uploaded_resume)
            st.sidebar.success("Resume parsed successfully.")
        except Exception as e:
            st.sidebar.error(f"Resume parsing failed: {e}")

    num_q = st.sidebar.slider("Number of questions", 3, 15, 7)
    difficulty = st.sidebar.selectbox("Difficulty", ["mixed", "easy", "medium", "hard"], index=0)
    use_llm = st.sidebar.checkbox("Use Gemini/OpenAI if API key is available", value=True)

    api_provider = st.sidebar.radio("LLM provider", ["Gemini", "OpenAI"], horizontal=True)

    api_key = None
    if api_provider == "Gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    else:
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        st.sidebar.info("No API key detected. The app will use local generation and evaluation.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Current dataset")
    st.sidebar.write(f"{len(st.session_state.question_bank):,} questions loaded")

    return role, role_norm, num_q, difficulty, use_llm, api_provider, api_key


def question_tab(role_norm, num_q, difficulty, use_llm, api_provider, api_key):
    st.subheader("Generate interview questions")

    cols = st.columns([2, 1])
    with cols[0]:
        st.write("Select a mode and generate a mock interview set.")
    with cols[1]:
        regenerate = st.button("Generate questions", use_container_width=True)

    if regenerate or not st.session_state.questions:
        st.session_state.questions = generate_questions(
            bank=st.session_state.question_bank,
            role=role_norm,
            count=num_q,
            difficulty=difficulty,
            resume_text=st.session_state.resume_text,
            use_llm=use_llm,
            api_provider=api_provider,
            api_key=api_key,
        )
        st.session_state.current_q_index = 0
        st.session_state.answers = {}

    if st.session_state.questions:
        st.success(f"Generated {len(st.session_state.questions)} questions for {role_norm.title()}.")
        for i, q in enumerate(st.session_state.questions, start=1):
            with st.expander(f"Q{i}. {q['question']}"):
                st.write(f"**Category:** {q.get('category', 'General')}")
                st.write(f"**Difficulty:** {q.get('difficulty', 'mixed')}")
                st.write(f"**Why asked:** {q.get('why', 'Role-relevant interview practice')}")
                st.write(f"**Expected points:** {q.get('ideal_points', 'N/A')}")
    else:
        st.info("Click Generate questions to start.")


def practice_tab(role_norm, use_llm, api_provider, api_key):
    st.subheader("Practice mode")

    if not st.session_state.questions:
        st.info("Generate questions first from the Questions tab.")
        return

    q_index = st.session_state.current_q_index
    q_index = min(q_index, len(st.session_state.questions) - 1)
    q = st.session_state.questions[q_index]

    st.markdown(f"### Question {q_index + 1}/{len(st.session_state.questions)}")
    st.write(q["question"])

    answer = st.text_area(
        "Your answer",
        value=st.session_state.answers.get(q_index, ""),
        height=180,
        placeholder="Type your answer here...",
        key=f"answer_{q_index}",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        prev_clicked = st.button("⬅ Previous", use_container_width=True)
    with col2:
        evaluate_clicked = st.button("Evaluate answer", use_container_width=True)
    with col3:
        next_clicked = st.button("Next ➡", use_container_width=True)

    if prev_clicked:
        st.session_state.current_q_index = max(0, q_index - 1)
        st.rerun()

    if next_clicked:
        st.session_state.answers[q_index] = answer
        st.session_state.current_q_index = min(len(st.session_state.questions) - 1, q_index + 1)
        st.rerun()

    if evaluate_clicked:
        st.session_state.answers[q_index] = answer
        result = evaluate_answer(
            question=q,
            answer=answer,
            role=role_norm,
            use_llm=use_llm,
            api_provider=api_provider,
            api_key=api_key,
            resume_text=st.session_state.resume_text,
        )
        st.session_state[f"result_{q_index}"] = result

    if f"result_{q_index}" in st.session_state:
        result = st.session_state[f"result_{q_index}"]
        st.markdown("### Feedback")
        st.metric("Score", f"{result['score']}/100")
        st.write(result["feedback"])
        with st.expander("Detailed rubric"):
            st.json(result["rubric"])
        if result.get("strengths"):
            st.success("Strengths: " + "; ".join(result["strengths"]))
        if result.get("improvements"):
            st.warning("Improve: " + "; ".join(result["improvements"]))


def dashboard_tab():
    st.subheader("Performance dashboard")

    results = []
    for i, q in enumerate(st.session_state.questions):
        if f"result_{i}" in st.session_state:
            r = st.session_state[f"result_{i}"]
            results.append({"question": q["question"], **r})

    avg, label = score_summary(results)
    a, b, c = st.columns(3)
    a.metric("Average score", f"{avg}/100")
    b.metric("Assessment", label)
    c.metric("Answered", f"{len(results)}/{len(st.session_state.questions) if st.session_state.questions else 0}")

    if results:
        df = pd.DataFrame(results)[["question", "score", "feedback"]]
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### Improvement themes")
        themes = {}
        for r in results:
            for imp in r.get("improvements", []):
                themes[imp] = themes.get(imp, 0) + 1
        if themes:
            theme_df = pd.DataFrame(sorted(themes.items(), key=lambda x: x[1], reverse=True), columns=["theme", "count"])
            st.bar_chart(theme_df.set_index("theme"))
    else:
        st.info("Evaluate some answers to see dashboard analytics.")


def main():
    init_state()
    render_header()

    role, role_norm, num_q, difficulty, use_llm, api_provider, api_key = sidebar_controls()

    tab1, tab2, tab3 = st.tabs(["Questions", "Practice", "Dashboard"])

    with tab1:
        question_tab(role_norm, num_q, difficulty, use_llm, api_provider, api_key)

    with tab2:
        practice_tab(role_norm, use_llm, api_provider, api_key)

    with tab3:
        dashboard_tab()

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Tip: Download a Kaggle interview question CSV and upload it from the sidebar. "
        "The app will use columns like role, question, category, difficulty, and ideal_points when available."
    )


if __name__ == "__main__":
    main()
