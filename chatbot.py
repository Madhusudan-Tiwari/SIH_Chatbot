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
        return detect(text)
    except LangDetectException:
        return "en"

def translate_text(text, src="auto", tgt="en"):
    if not text:
        return ""
    if src == tgt:
        return text
    try:
        translated = GoogleTranslator(
            source=src if src != "auto" else "auto", target=tgt
        ).translate(text)
        return translated
    except Exception as e:
        st.warning(f"Translation service error (proceeding without translation): {str(e)}")
        return text

def best_match(query_en, qa_list, top_k=TOP_K):
    """Return a list of top_k matches with their scores."""
    questions = [item["question"] for item in qa_list]
    results = process.extract(query_en, questions, scorer=fuzz.token_set_ratio, limit=top_k)
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
    src_lang = detect_language(user_input)
    query_en = translate_text(user_input, src=src_lang, tgt=LANGUAGE_FOR_MATCHING)
    matches = best_match(query_en, qa_list)
    if not matches:
        return {"answer": None, "score": 0, "matches": [], "src_lang": src_lang}

    best = matches[0]
    if best["score"] < conf_thresh:
        return {
            "answer": None,
            "score": best["score"],
            "matches": matches,
            "src_lang": src_lang,
            "query_en": query_en,
        }
    answer_translated = translate_text(best["answer"], src=LANGUAGE_FOR_MATCHING, tgt=src_lang)
    return {
        "answer": answer_translated,
        "score": best["score"],
        "matches": matches,
        "src_lang": src_lang,
        "query_en": query_en,
    }

# ------------------- Streamlit UI -------------------
st.set_page_config(page_title="FAQ Chatbot", page_icon="🎓", layout="centered")

st.title("🎓 FAQ Chatbot (Prototype)")
st.markdown(
    """
    > This is a **prototype chatbot** that uses fuzzy matching on an FAQ dataset.  
    > It **does not use LLMs** currently — answers are chosen based on similarity scores.  
    > ✅ Supports **English, Hindi, and Punjabi** (via auto-detection + translation).  
    > 🔮 *Future versions will integrate LLM + vector search for smarter conversations.*  
    """
)

# Load FAQs
try:
    faqs = load_faqs(JSON_PATH)
except Exception as e:
    st.error(f"Could not load FAQs: {e}")
    st.stop()

# Sidebar options
st.sidebar.markdown("### ⚙️ Options")
show_raw = st.sidebar.checkbox("Show raw matching candidates", value=False)
top_k = st.sidebar.slider("Top-k candidates to show", 1, 10, 5)
CONFIDENCE_THRESHOLD = st.sidebar.slider("Confidence threshold (%)", 0, 100, 60)

# Initialize history
if "history" not in st.session_state:
    st.session_state["history"] = []

# Render conversation history
st.subheader("💬 Conversation")
for role, content in st.session_state["history"]:
    with st.chat_message(role):
        st.markdown(content)

# Chat input
user_input = st.chat_input("Type your question here...")

if user_input:
    # Show user message
    st.session_state["history"].append(("user", user_input))
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.spinner("🔎 Finding an answer..."):
        result = get_answer(user_input.strip(), faqs, conf_thresh=CONFIDENCE_THRESHOLD)

    if result["answer"]:
        bot_reply = f"✅ {result['answer']}  \n\n📊 Confidence: **{result['score']}%**"
    else:
        bot_reply = f"❌ Sorry — no confident match (best score {result['score']}%)."

        if result.get("matches"):
            bot_reply += "\n\n**Closest matches:**"
            for i, m in enumerate(result["matches"][:top_k], start=1):
                bot_reply += f"\n- **Q:** {m['question']}  \n➡️ {m['answer']} (Score: {m['score']}%)"

    # Save bot reply
    st.session_state["history"].append(("assistant", bot_reply))
    with st.chat_message("assistant"):
        st.markdown(bot_reply)

# Optional: show entire FAQ list
with st.expander("📖 Show full FAQ list"):
    for item in faqs:
        st.markdown(f"**❓ {item['question']}**")
        st.write(f"➡️ {item['answer']}")
        st.write("---")

# Footer disclaimer
st.markdown(
    """
    ---
    ⚠️ *Disclaimer:* This chatbot is a **prototype** and currently uses fuzzy string matching, not an LLM.  
    Answers are selected from pre-loaded FAQs.  
    """
)
