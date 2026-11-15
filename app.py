"""
AI Escape Room - Version 1 (naive version)

The LLM is the Game Master AND the rulebook. All puzzle solutions live inside
the system prompt, and the model decides by itself what works and what doesn't.
This is intentionally simple. Version 2 fixes its weaknesses.
"""

import os
import time

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
MODELS = [
    m.strip()
    for m in os.getenv(
        "GROQ_MODELS", "llama-3.3-70b-versatile,llama-3.1-8b-instant"
    ).split(",")
]

SYSTEM_PROMPT = """
You are the Game Master of a text escape room. The player is locked in an old library.
Stay in character, describe things in 2-4 short sentences, and never break the story.

ROOM OBJECTS (only these exist): desk, bookshelf, painting, locked drawer, door.

SECRET LAYOUT (never reveal it directly, the player must discover it step by step):
- Desk: holds an old diary. The diary says: "I hid my numbers in four books.
  Read them in the order they stand on the shelf." It does not give the numbers.
- Bookshelf: four books stand out from the others. Their first pages carry handwritten
  numbers, from left to right: 7, 3, 1, 9. Only show these when the player examines the books.
- Locked drawer: opens only with the code 7319. Inside is a torn note:
  "The exit code begins with 48. The rest is hidden behind the eyes of the portrait."
- Painting: a portrait with very watchful eyes. If the player looks behind it or lifts it,
  they find a scrap of paper with the numbers 15 written on it.
- Door: has a four-digit keypad. The correct code is 4815 (48 from the note, 15 from the painting).

RULES:
1. Reveal information only when the player examines the right object.
2. The drawer stays locked until the player enters 7319.
3. The door stays locked until the player enters 4815.
4. Do not invent new objects, items or exits.
5. When the player enters 4815 on the door, describe their escape and include the exact
   tag [ESCAPED] at the end of your message. Never use that tag at any other time.
6. Keep answers short. If the player seems stuck, give a gentle hint, not the answer.
"""

INTRO = (
    "You wake up on a cold wooden floor inside a locked library. "
    "Dust hangs in the air. You see a desk, a bookshelf, a painting, "
    "a locked drawer and a heavy door with a four-digit keypad."
)

# timeout is in seconds, so a stuck call ends instead of hanging forever
client = Groq(api_key=API_KEY, timeout=30.0) if API_KEY else None


def ask_game_master(messages):
    """Send the system prompt plus the whole chat history to the model.
    If one model fails, try the next one in the list."""
    chat = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    last_error = None
    for model in MODELS:
        for attempt in range(2):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=chat,
                    temperature=0.7,
                )
                return response.choices[0].message.content or "..."
            except Exception as e:
                last_error = e
                time.sleep(2)
    raise last_error


# ---------------------------------------------------------------------------
# Streamlit interface
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Escape Room v1", page_icon="🔐")
st.title("🔐 AI Escape Room - Version 1")

if client is None:
    st.error("GROQ_API_KEY not found. Create a .env file (see .env.example).")
    st.stop()

# Session state keeps the chat and the win flag between reruns
if "messages" not in st.session_state:
    st.session_state.messages = []
if "escaped" not in st.session_state:
    st.session_state.escaped = False

with st.sidebar:
    st.header("How to play")
    st.write(
        "Type what you want to do, like 'examine the bookshelf' or "
        "'try 1234 on the drawer'. Find clues, solve the puzzles and open the door."
    )
    if st.button("Restart game"):
        st.session_state.messages = []
        st.session_state.escaped = False
        st.rerun()

st.info(INTRO)

# Show the conversation so far
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

if st.session_state.escaped:
    st.success("🎉 You escaped the library! Press 'Restart game' to play again.")
    st.balloons()
else:
    user_text = st.chat_input("What do you do?")
    if user_text:
        st.session_state.messages.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.write(user_text)

        with st.chat_message("assistant"):
            try:
                reply = ask_game_master(st.session_state.messages)
            except Exception as e:
                reply = f"(Game Master error: {e})"

            # Win detection: the LLM adds [ESCAPED] when the door opens
            if "[ESCAPED]" in reply:
                st.session_state.escaped = True
                reply = reply.replace("[ESCAPED]", "").strip()
            st.write(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        if st.session_state.escaped:
            st.rerun()