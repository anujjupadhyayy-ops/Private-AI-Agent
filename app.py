# ── IMPORTS ───────────────────────────────────────────────────────────────────

from db import get_conn
# Imports the database connection function from db.py
# Single source of truth — all database connections go through this one function
# Means switching databases only requires changing db.py, nothing else

import streamlit as st
# Streamlit converts Python code into a web interface
# Every st.title(), st.button(), st.chat_input() call renders a UI element
# Runs at localhost:8501 — accessible in any browser on your Mac

from agent import run_agent
# Imports the main agent function — this is what processes user messages
# run_agent(message, session_id) → returns the AI's response as a string

import bcrypt
# Password hashing library — used to verify login credentials
# bcrypt is deliberately slow to make brute-force attacks impractical

# ── PAGE CONFIGURATION ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="My Private AI",     # Text shown in browser tab
    page_icon="🔒",                  # Icon shown in browser tab
    layout="centered"               # Centers content — "wide" would use full width
)
# Must be the first Streamlit command called — Streamlit throws an error if anything renders before this

# ── AUTHENTICATION ────────────────────────────────────────────────────────────

def verify_user(username: str, password: str):
    # Checks if the username exists and the password matches
    # Returns a user dictionary if valid, None if invalid
    # Never returns the password hash — only safe fields
    
    conn = get_conn()
    # Opens a connection to PostgreSQL
    
    cursor = conn.cursor()
    # Creates a cursor — required by psycopg2 (PostgreSQL adapter)
    # SQLite lets you call conn.execute() directly, PostgreSQL requires a cursor
    
    cursor.execute(
        "SELECT id, username, password, role FROM users WHERE username=%s",
        [username]
        # %s is PostgreSQL's placeholder syntax (SQLite uses ?)
        # Passing username as a parameter prevents SQL injection attacks
        # SQL injection = malicious input that manipulates the query structure
    )
    row = cursor.fetchone()
    # Fetches the first (and only) matching row
    # Returns None if no user found with that username
    
    conn.close()
    # Always close the connection — prevents connection pool exhaustion
    
    if not row:
        return None
        # Username doesn't exist in the database
    
    stored_hash = row[2].encode()
    # row[2] is the password column (3rd column in SELECT)
    # .encode() converts string to bytes — bcrypt requires bytes not strings
    
    if bcrypt.checkpw(password.encode(), stored_hash):
        # checkpw hashes the entered password and compares to stored hash
        # Timing-safe comparison — prevents timing attacks
        # Returns True if passwords match, False otherwise
        return {"id": str(row[0]), "username": row[1], "role": row[3]}
        # Returns safe user data — never returns the password hash
        # str(row[0]) converts the integer ID to string for session storage
    return None
    # Password didn't match

def show_login():
    # Renders the login form — called when no user is in session state
    
    st.title("🔒 Private AI")
    st.caption("Enter your credentials to continue")
    
    with st.form("login_form"):
        # st.form groups inputs together — prevents Streamlit re-running
        # on every keystroke, only runs when the submit button is clicked
        
        username = st.text_input("Username")
        # Renders a text input field, stores value in username variable
        
        password = st.text_input("Password", type="password")
        # type="password" masks the input with dots — never shows plain text
        
        submitted = st.form_submit_button("Login")
        # Renders the submit button — submitted=True only when clicked
        
        if submitted:
            if not username or not password:
                st.error("Please enter both username and password")
                return
                # Exits the function early — prevents calling verify_user with empty strings
            
            user = verify_user(username, password)
            if user:
                st.session_state.user = user
                # session_state persists data across Streamlit reruns
                # Without session_state, all variables reset on every interaction
                
                st.session_state.session_id = f"user_{user['id']}"
                # Creates a unique session ID per user
                # All messages stored under this ID in the database
                # user_1 sees only their messages, user_2 sees only theirs
                
                st.rerun()
                # Forces Streamlit to re-execute the script from the top
                # On rerun, "user" is now in session_state, so the login form is skipped
            else:
                st.error("Invalid username or password")
                # Deliberately vague — doesn't reveal whether username or password was wrong

# ── AUTHENTICATION GATE ───────────────────────────────────────────────────────

if "user" not in st.session_state:
    show_login()
    # If no logged-in user exists, show the login form
    st.stop()
    # st.stop() halts execution here — nothing below renders until user is logged in
    # This is the security gate — the entire chat interface is behind this check

user = st.session_state.user
# Shorthand — instead of typing st.session_state.user everywhere, use 'user'

# ── DATABASE FUNCTIONS ────────────────────────────────────────────────────────

def load_history():
    # Retrieves all messages for the current user's session from PostgreSQL
    # Called on every page load to restore conversation history
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE session_id=%s ORDER BY timestamp",
        [st.session_state.session_id]
        # Filters to only this user's messages using their session_id
        # ORDER BY timestamp ensures messages appear in chronological order
    )
    rows = cursor.fetchall()
    # fetchall() returns all matching rows as a list of tuples
    conn.close()
    return rows
    # Returns list of (role, content) tuples e.g. [("user", "hello"), ("assistant", "hi")]

def save_msg(role, content):
    # Saves a single message to PostgreSQL
    # Called after every user message and every AI response
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages(session_id,role,content) VALUES(%s,%s,%s)",
        [st.session_state.session_id, role, content]
        # session_id links message to this specific user
        # role is either "user" or "assistant"
        # content is the actual message text
        # timestamp is set automatically by PostgreSQL DEFAULT CURRENT_TIMESTAMP
    )
    conn.commit()
    # commit() makes the INSERT permanent — without it the data would be lost

# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:
    # Everything inside this block renders in the left sidebar panel
    
    st.markdown(f"### 👤 {user['username']}")
    # Shows the logged-in username with a person emoji
    
    st.markdown(f"Role: `{user['role']}`")
    # Shows the user's role (admin or user) in a code-style block
    
    st.divider()
    # Renders a horizontal line to separate user info from buttons
    
    if st.button("🗑️ Clear conversation"):
        # Renders a button — the if block runs only when clicked
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM messages WHERE session_id=%s",
            [st.session_state.session_id]
            # Deletes ONLY this user's messages — other users' history is untouched
        )
        conn.commit()
        st.success("Conversation cleared")
        # Shows a green success message
        st.rerun()
        # Reruns the page so the cleared history takes effect immediately
    
    if st.button("🚪 Logout"):
        del st.session_state.user
        # Removes the user from session state
        del st.session_state.session_id
        # Removes the session ID
        st.rerun()
        # On rerun, "user" is no longer in session_state
        # The authentication gate at the top triggers, showing the login form again

# ── CHAT INTERFACE ────────────────────────────────────────────────────────────

st.title("🔒 My Private AI")
st.caption("Running locally on your Mac · Nothing leaves this machine")

for role, content in load_history():
    # Loops through all previous messages for this session
    with st.chat_message(role):
        # st.chat_message renders a chat bubble — "user" on right, "assistant" on left
        st.write(content)
        # Writes the message text inside the bubble

# ── VOICE INPUT ───────────────────────────────────────────────────────────────

try:
    from voice import record_and_transcribe
    # Tries to import the voice module — only available if sounddevice and whisper installed
    
    if st.button("🎤 Speak (5 sec)"):
        # Renders the mic button — only appears if voice import succeeded
        with st.spinner("Listening..."):
            transcript = record_and_transcribe(duration=5)
            # Records 5 seconds of audio from your microphone
            # Whisper (running locally) converts speech to text
            # Nothing is sent to any cloud service
        
        st.write(f"You said: {transcript}")
        # Shows the transcribed text so you can verify it was heard correctly
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = run_agent(transcript, st.session_state.session_id)
                # Passes transcribed text to the agent exactly like a typed message
            st.write(response)
        
        save_msg("user", transcript)
        # Saves the transcribed speech as a user message
        save_msg("assistant", response)
        # Saves the AI response
except Exception:
    pass
    # If voice import fails (missing packages, no microphone), silently skip
    # The rest of the app continues working normally — voice is optional

# ── TEXT CHAT INPUT ───────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask me anything..."):
    # st.chat_input renders the text box at the bottom of the screen
    # The := (walrus operator) assigns the input value AND checks if it's not empty
    # This block only runs when the user submits a message
    
    with st.chat_message("user"):
        st.write(prompt)
        # Immediately shows the user's message in a chat bubble
        # Appears instantly before the AI starts thinking
    
    save_msg("user", prompt)
    # Saves the user message to PostgreSQL immediately
    # If the app crashes during AI processing, the user message is already saved
    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = run_agent(prompt, st.session_state.session_id)
            # Calls the LangGraph agent with the message and session ID
            # Agent loads history, runs the ReAct loop, calls tools, returns response
            # This is the slowest step — model inference takes seconds
        st.write(response)
        # Renders the AI response in an assistant chat bubble
    
    save_msg("assistant", response)
    # Saves the AI response to PostgreSQL
    # Both messages now permanently stored — survive app restarts