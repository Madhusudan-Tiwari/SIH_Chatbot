# chatbot.py
import json
import streamlit as st
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
from rapidfuzz import fuzz, process
import os

# --------- Configuration ----------
JSON_PATH = "combined_extracted_qa.json"  # change if your file is named differently
LANGUAGE_FOR_MATCHING = "en"  # we translate everything to English for matching
TOP_K = 5
CONFIDENCE_THRESHOLD = 60  # percent; below this we return a fallback message
# ----------------------------------

@st.cache_data
def load_faqs(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"FAQ JSON not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Expecting list of objects with keys "question" and "answer"
    qa = []
    for item in data:
        q = item.get("question") or item.get("q") or item.get("title") or ""
        a = item.get("answer") or item.get("ans") or ""
        if q:
            qa.append({"question": q.strip(), "answer": a.strip()})
    return qa

def detect_language(text):
    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        return "en"

def translate_text(text, src="auto", tgt="en"):
    if not text:
        return ""
    if src == tgt:
        return text
    try:
        # deep-translator requires explicit source sometimes; "auto" works usually
        translated = GoogleTranslator(source=src if src != "auto" else "auto", target=tgt).translate(text)
        return translated
    except Exception as e:
        # if translator fails, return original text to avoid crashing
        st.warning(f"Translation service error (proceeding without translation): {str(e)}")
        return text

def best_match(query_en, qa_list, top_k=TOP_K):
    """
    Returns a list of top_k matches with their scores.
    Uses RapidFuzz process.extract for good performance and accurate fuzzy scores.
    """
    questions = [item["question"] for item in qa_list]
    # process.extract returns tuples (match, score, index)
    results = process.extract(query_en, questions, scorer=fuzz.token_set_ratio, limit=top_k)
    # Convert to structured records
    matches = []
    for match_text, score, idx in results:
        matches.append({
            "question": questions[idx],
            "answer": qa_list[idx]["answer"],
            "score": score,
            "index": idx
        })
    return matches

def get_answer(user_input, qa_list, conf_thresh=CONFIDENCE_THRESHOLD):
    # Step 1: detect language
    src_lang = detect_language(user_input)
    # Step 2: translate to English for matching
    query_en = translate_text(user_input, src=src_lang, tgt=LANGUAGE_FOR_MATCHING)
    # Step 3: find best matches
    matches = best_match(query_en, qa_list)
    if not matches:
        return {"answer": None, "score": 0, "matches": [], "src_lang": src_lang}

    best = matches[0]
    # If score below threshold — treat as not found
    if best["score"] < conf_thresh:
        # return top matches along with low confidence
        return {"answer": None, "score": best["score"], "matches": matches, "src_lang": src_lang, "query_en": query_en}
    # Otherwise translate answer back to user language (if needed)
    answer_translated = translate_text(best["answer"], src=LANGUAGE_FOR_MATCHING, tgt=src_lang)
    return {"answer": answer_translated, "score": best["score"], "matches": matches, "src_lang": src_lang, "query_en": query_en}

# ------------------- Streamlit UI -------------------
st.set_page_config(page_title="RTU FAQ Chatbot", page_icon="🎓", layout="centered")
st.title("RTU FAQ Chatbot")
st.caption("Ask questions about admissions / reporting. (Uses fuzzy matching against the extracted FAQ JSON)")

# Load FAQs
try:
    faqs = load_faqs(JSON_PATH)
except Exception as e:
    st.error(f"Could not load FAQs: {e}")
    st.stop()

st.sidebar.markdown("### App options")
show_raw = st.sidebar.checkbox("Show raw matching candidates", value=False)
top_k = st.sidebar.slider("Top-k candidates to show", min_value=1, max_value=10, value=5)
CONFIDENCE_THRESHOLD = st.sidebar.slider("Confidence threshold (%)", min_value=0, max_value=100, value=60)

# Chat input
with st.form("ask_form", clear_on_submit=False):
    user_input = st.text_area("Your question", height=100, placeholder="E.g. Where do I report at RTU?")
    submitted = st.form_submit_button("Ask")

if submitted:
    if not user_input or not user_input.strip():
        st.warning("Please type a question.")
    else:
        with st.spinner("Finding an answer..."):
            result = get_answer(user_input.strip(), faqs, conf_thresh=CONFIDENCE_THRESHOLD)
        if result["answer"]:
            st.success(result["answer"])
            st.write(f"**Match confidence:** {result['score']}%")
            if show_raw:
                st.write("---")
                st.write("Top matching FAQ candidates (English-translated query used for matching):")
                st.write(f"**Translated query →** {result.get('query_en','')}")
                for i, m in enumerate(result["matches"][:top_k], start=1):
                    st.write(f"{i}. **Q:** {m['question']}")
                    st.write(f"   - Score: {m['score']}%")
                    st.write(f"   - A: {m['answer']}")
        else:
            st.error("Sorry — I couldn't find a confident match in the FAQ.")
            st.write(f"Best match confidence: {result['score']}%")
            if result.get("matches"):
                st.write("Here are the top candidates I found — maybe one of these helps:")
                for i, m in enumerate(result["matches"][:top_k], start=1):
                    st.write(f"{i}. **Q:** {m['question']}  —  **score:** {m['score']}%")
                    st.write(f"   A: {m['answer']}")
            st.write("If none apply, try rephrasing your question or contact admissions at udadmissions@rtu.ac.in")

# Optional: show entire FAQ list for inspection (collapsible)
with st.expander("Show full FAQ list"):
    for item in faqs:
        st.markdown(f"**{item['question']}**")
        st.write(item['answer'])
        st.write("---")
