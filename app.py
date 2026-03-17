from db import get_conn
import streamlit as st
from agent import run_agent
import bcrypt

st.set_page_config(
    page_title="My Private AI",
    page_icon="🔒",
    layout="centered"
)

def verify_user(username: str, password: str):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, password, role FROM users WHERE username=%s",
        [username]
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    stored_hash = row[2].encode()
    if bcrypt.checkpw(password.encode(), stored_hash):
        return {"id": str(row[0]), "username": row[1], "role": row[3]}
    return None

def show_login():
    st.title("🔒 Private AI")
    st.caption("Enter your credentials to continue")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            if not username or not password:
                st.error("Please enter both username and password")
                return
            user = verify_user(username, password)
            if user:
                st.session_state.user = user
                st.session_state.session_id = f"user_{user['id']}"
                st.rerun()
            else:
                st.error("Invalid username or password")

if "user" not in st.session_state:
    show_login()
    st.stop()

user = st.session_state.user

def load_history():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE session_id=%s ORDER BY timestamp",
        [st.session_state.session_id]
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_msg(role, content):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages(session_id,role,content) VALUES(%s,%s,%s)",
        [st.session_state.session_id, role, content]
    )
    conn.commit()

with st.sidebar:
    st.markdown(f"### 👤 {user['username']}")
    st.markdown(f"Role: `{user['role']}`")
    st.divider()
    if st.button("🗑️ Clear conversation"):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM messages WHERE session_id=%s",
            [st.session_state.session_id]
        )
        conn.commit()
        st.success("Conversation cleared")
        st.rerun()
    if st.button("🚪 Logout"):
        del st.session_state.user
        del st.session_state.session_id
        st.rerun()

st.title("🔒 My Private AI")
st.caption("Running locally on your Mac · Nothing leaves this machine")

for role, content in load_history():
    with st.chat_message(role):
        st.write(content)

try:
    from voice import record_and_transcribe
    if st.button("🎤 Speak (5 sec)"):
        with st.spinner("Listening..."):
            transcript = record_and_transcribe(duration=5)
        st.write(f"You said: {transcript}")
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = run_agent(transcript, st.session_state.session_id)
            st.write(response)
        save_msg("user", transcript)
        save_msg("assistant", response)
except Exception:
    pass

if prompt := st.chat_input("Ask me anything..."):
    with st.chat_message("user"):
        st.write(prompt)
    save_msg("user", prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = run_agent(prompt, st.session_state.session_id)
        st.write(response)
    save_msg("assistant", response)