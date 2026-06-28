import streamlit as st
import requests
import re
from config import LEAD_CAPTURE

API_BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="AI Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .message { padding: 1rem; margin: 0.5rem 0; border-radius: 15px; max-width: 80%; word-wrap: break-word; }
    .user-message { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; margin-left: auto; text-align: right; }
    .assistant-message { background: #f0f0f0; color: #333; margin-right: auto; }
</style>
""", unsafe_allow_html=True)

# =========================
# SESSION STATE
# =========================

for key, default in {
    'page': 'welcome',
    'session_id': None,
    'user_info': {},
    'messages': [],
    'chat_disabled': False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =========================
# VALIDATION
# =========================

def validate_email(email):
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email.strip()) is not None

def validate_contact(contact):
    cleaned = re.sub(r'[\s\-\(\)]', '', contact.strip())
    digits = re.sub(r'[^\d]', '', cleaned)
    return len(digits) >= 7

# =========================
# API CALLS
# =========================

def init_session(name, email, contact=None):
    try:
        payload = {"user_info": {"name": name, "email": email}}
        if LEAD_CAPTURE and contact:
            payload["user_info"]["contact"] = contact
        res = requests.post(f"{API_BASE_URL}/init-session", json=payload)
        return res.json() if res.status_code == 200 else None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def send_message(session_id, user_input):
    try:
        res = requests.post(f"{API_BASE_URL}/chat", json={"session_id": session_id, "user_input": user_input})
        return res.json() if res.status_code == 200 else None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def start_new_chat(session_id):
    try:
        res = requests.post(f"{API_BASE_URL}/new-chat", json={"session_id": session_id})
        return res.json() if res.status_code == 200 else None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

# =========================
# PAGES
# =========================

def show_welcome_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 4rem 2rem;">
            <h1 style="font-size:3rem; font-weight:800;">🤖 AI Assistant</h1>
            <p style="color:#666; font-size:1.2rem;">Powered by your config</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("💬 Start Chat", use_container_width=True, type="primary"):
            st.session_state.page = 'form'
            st.rerun()


def show_form_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 📝 Tell us about yourself")
        with st.form("user_info_form"):
            name = st.text_input("Full Name *", placeholder="Enter your name")
            email = st.text_input("Email *", placeholder="example@email.com")

            # Contact sirf tab dikhao jab LEAD_CAPTURE = True
            contact = None
            if LEAD_CAPTURE:
                contact = st.text_input("Contact Number *", placeholder="+1234567890")

            col_a, col_b = st.columns(2)
            with col_a:
                submitted = st.form_submit_button("✅ Start Chat", use_container_width=True, type="primary")
            with col_b:
                cancel = st.form_submit_button("❌ Cancel", use_container_width=True)

        if cancel:
            st.session_state.page = 'welcome'
            st.rerun()

        if submitted:
            errors = []
            if not name or len(name.strip()) < 2:
                errors.append("Please enter a valid name")
            if not email or not validate_email(email):
                errors.append("Please enter a valid email")
            if LEAD_CAPTURE and (not contact or not validate_contact(contact)):
                errors.append("Please enter a valid contact number")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                with st.spinner("Initializing..."):
                    result = init_session(
                        name.strip(),
                        email.strip(),
                        contact.strip() if contact else None
                    )
                    if result:
                        st.session_state.session_id = result['session_id']
                        st.session_state.user_info = {"name": name.strip(), "email": email.strip()}
                        st.session_state.messages = [{"role": "assistant", "content": result['message']}]
                        st.session_state.page = 'chat'
                        st.session_state.chat_disabled = False
                        st.rerun()


def show_chat_page():
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 New Chat", type="secondary"):
            result = start_new_chat(st.session_state.session_id)
            if result:
                st.session_state.messages = [{"role": "assistant", "content": result['message']}]
                st.session_state.chat_disabled = False
                st.rerun()

    st.markdown(f"**Chat** — Welcome, {st.session_state.user_info.get('name', 'User')}!")

    # Messages
    for message in st.session_state.messages:
        if message['role'] == 'user':
            st.markdown(f"""
            <div style="display:flex; justify-content:flex-end; margin:0.5rem 0;">
                <div class="message user-message">{message['content']}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="display:flex; justify-content:flex-start; margin:0.5rem 0;">
                <div class="message assistant-message">{message['content']}</div>
            </div>""", unsafe_allow_html=True)

    # Input
    if not st.session_state.chat_disabled:
        with st.form("chat_form", clear_on_submit=True):
            col_a, col_b = st.columns([5, 1])
            with col_a:
                user_input = st.text_input("Message", placeholder="Type here...", label_visibility="collapsed")
            with col_b:
                send = st.form_submit_button("📤 Send", use_container_width=True, type="primary")

            if send and user_input.strip():
                st.session_state.messages.append({"role": "user", "content": user_input.strip()})
                with st.spinner("Typing..."):
                    result = send_message(st.session_state.session_id, user_input.strip())
                    if result:
                        st.session_state.messages.append({"role": "assistant", "content": result['response']})
                        if result.get('conversation_ended', False):
                            st.session_state.chat_disabled = True
                st.rerun()
    else:
        st.info("💬 Chat ended. Click 'New Chat' to start again!")

# =========================
# MAIN
# =========================

def main():
    if st.session_state.page == 'welcome':
        show_welcome_page()
    elif st.session_state.page == 'form':
        show_form_page()
    elif st.session_state.page == 'chat':
        show_chat_page()

if __name__ == "__main__":
    main()