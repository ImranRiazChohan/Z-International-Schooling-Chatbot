import re
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import SPREADSHEET_ID, GOOGLE_CREDS_FILE, SOCIAL_LINKS

def validate_email(email):
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email.strip()) is not None

def validate_contact(contact):
    cleaned = re.sub(r'[\s\-\(\)]', '', contact.strip())
    digits = re.sub(r'[^\d]', '', cleaned)
    return len(digits) >= 7

def validate_name(name):
    return len(name.strip()) >= 2

def is_goodbye(text):
    patterns = [r'\b(bye|goodbye|thanks|thank you|that\'s all|no thanks|not interested)\b']
    return any(re.search(p, text.lower()) for p in patterns)

def is_demo_intent(text):
    patterns = [r'\b(book.*demo|schedule.*demo|i\'?m interested|sign me up|let\'s (do|schedule|book))\b']
    return any(re.search(p, text.lower()) for p in patterns)

def is_confirmation(text):
    return bool(re.search(r'\b(yes|confirm|correct|looks good|yep|yeah)\b', text.lower()))

def wants_change(text):
    return bool(re.search(r'\b(change|update|wrong|edit|incorrect)\b', text.lower()))

def detect_field_to_change(text):
    t = text.lower()
    if re.search(r'\b(name)\b', t): return 'name'
    if re.search(r'\b(email)\b', t): return 'email'
    if re.search(r'\b(contact|phone|number|mobile)\b', t): return 'contact'
    return None

def get_goodbye_message(user_name):
    msg = f"Thank you for chatting{', ' + user_name if user_name else ''}! 😊\n\n"
    for platform, link in SOCIAL_LINKS.items():
        msg += f"{platform.capitalize()}: {link}\n\n"
    return msg

def save_to_sheets(user_info: dict):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        col_values = sheet.col_values(1)
        session_id = user_info.get("session_id", "")
        row = [session_id, user_info.get("name",""), user_info.get("email",""), user_info.get("contact",""), timestamp]
        try:
            idx = col_values.index(session_id) + 1
            sheet.update(f"A{idx}:E{idx}", [row])
        except ValueError:
            sheet.append_row(row)
        return True
    except Exception as e:
        print(f"Sheets error: {e}")
        return False

def handle_lead_flow(user_input, session, user_info):
    """
    Returns (response_text, conversation_ended) or None if not in lead flow.
    Manages: awaiting_field, awaiting_confirmation states.
    """
    user_name = user_info["name"]
    user_email = user_info["email"]
    user_contact = user_info.get("contact", "")

    # --- Awaiting a specific field update ---
    if session["awaiting_field"]:
        field = session["awaiting_field"]
        validators = {"email": validate_email, "contact": validate_contact, "name": validate_name}
        error_msgs = {
            "email": "That email doesn't look valid. Please try again (e.g. name@example.com).",
            "contact": "Please provide a valid phone number (e.g. +1234567890).",
            "name": "Please provide a valid name (at least 2 characters)."
        }
        if validators[field](user_input):
            user_info[field] = user_input
            save_to_sheets(user_info)
            summary = f"- Name: {user_info['name']}\n- Email: {user_info['email']}\n- Contact: {user_info['contact']}"
            session["awaiting_field"] = None
            session["awaiting_confirmation"] = True
            return f"Thanks! Please confirm:\n\n{summary}\n\nReply `yes` or tell me what to change.", False
        else:
            return error_msgs[field], False

    # --- Awaiting confirmation ---
    if session["awaiting_confirmation"]:
        if is_confirmation(user_input):
            save_to_sheets(user_info)
            session["awaiting_confirmation"] = False
            return "Great! Our team will reach out to you shortly to schedule your demo.", False
        elif wants_change(user_input):
            field = detect_field_to_change(user_input)
            if field:
                session["awaiting_field"] = field
                session["awaiting_confirmation"] = False
                return f"Sure — please provide the new {field}.", False
            return "Which detail would you like to change? (name / email / contact)", False
        else:
            return "Reply `yes` to confirm, or tell me what you'd like to change.", False

    # --- Demo intent detected ---
    if is_demo_intent(user_input):
        if not user_contact or not user_contact.strip():
            session["awaiting_field"] = "contact"
            return "To schedule your demo, I'll need your contact number. Please share it.", False
        summary = f"- Name: {user_name}\n- Email: {user_email}\n- Contact: {user_contact}"
        session["awaiting_confirmation"] = True
        return f"Please confirm your details:\n\n{summary}\n\nReply `yes` to confirm.", False

    return None  # Not in lead flow — let RAG handle it