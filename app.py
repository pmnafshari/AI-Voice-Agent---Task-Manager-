
import streamlit as st
import speech_recognition as sr
import google.generativeai as genai
import os
import json
import asyncio
import edge_tts
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from audiorecorder import audiorecorder
from notion_client import Client

# --- 1. Language & Voice Settings ---
LANG_CONFIG = {
    "Persian 🇮🇷": {
        "code": "fa-IR", 
        "voice": "fa-IR-DilaraNeural", 
        "sys_prompt": "Persian"
    },
    "English 🇺🇸": {
        "code": "en-US", 
        "voice": "en-US-JennyNeural", 
        "sys_prompt": "English"
    },
    "Italian 🇮🇹": {
        "code": "it-IT", 
        "voice": "it-IT-ElsaNeural", 
        "sys_prompt": "Italian"
    }
}

TRANSLATIONS = {
    "Persian": {
        "added": "به لیست کارهات اضافه شد.",
        "save_error": "نتوانستم در نوشن ذخیره کنم. خطا: {}",
        "not_found": "هیچ تسکی با نام '{}' پیدا نکردم.",
        "updated": "تسک '{}' بروزرسانی شد.",
        "update_error": "خطا در بروزرسانی: {}",
        "deleted": "تسک '{}' حذف شد.",
        "delete_error": "خطا در حذف: {}",
        "rate_limit": "⚠️ کمی صبر کنید! سیستم شلوغ است.",
        "generic_error": "اوپس، مشکلی پیش آمد: {}",
        "listening": "🎧 گوش می‌کنم...",
        "thinking": "🧠 فکر می‌کنم...",
        "retry": "متوجه نشدم. لطفا دوباره بگویید.",
        "stop": "🚫 تنظیمات پیدا نشد.",
        "tasks_header": "📅 تسک‌های شما:",
        "no_tasks": "هیچ تسکی برای این بازه زمانی ندارید.",
        "read_error": "خطا در خواندن تسک‌ها: {}"
    },
    "English": {
        "added": "I've added that to your list.",
        "save_error": "I couldn't save that to Notion. Error: {}",
        "not_found": "I couldn't find any task matching '{}'.",
        "updated": "Updated '{}'.",
        "update_error": "Update Error: {}",
        "deleted": "Deleted '{}'.",
        "delete_error": "Delete Error: {}",
        "rate_limit": "⚠️ I'm a bit overwhelmed right now (Rate Limit). Give me a minute to catch my breath!",
        "generic_error": "Oops, something went wrong: {}",
        "listening": "🎧 I'm all ears...",
        "thinking": "🧠 Let me think about that...",
        "retry": "Sorry, I didn't catch that. Could you please repeat?",
        "stop": "🚫 Settings not found.",
        "tasks_header": "📅 Your Tasks:",
        "no_tasks": "You have no tasks for this period.",
        "read_error": "Error reading tasks: {}"
    },
    "Italian": {
        "added": "Aggiunto alla tua lista.",
        "save_error": "Non sono riuscito a salvare su Notion. Errore: {}",
        "not_found": "Non ho trovato nessun compito corrispondente a '{}'.",
        "updated": "Aggiornato '{}'.",
        "update_error": "Errore aggiornamento: {}",
        "deleted": "Eliminato '{}'.",
        "delete_error": "Errore eliminazione: {}",
        "rate_limit": "⚠️ Sono un po' sovraccarico (Rate Limit). Dammi un minuto!",
        "generic_error": "Ops, qualcosa è andato storto: {}",
        "listening": "🎧 Ti ascolto...",
        "thinking": "🧠 Fammi pensare...",
        "retry": "Non ho capito. Puoi ripetere?",
        "stop": "🚫 Impostazioni non trovate.",
        "tasks_header": "📅 I tuoi compiti:",
        "no_tasks": "Non hai compiti per questo periodo.",
        "read_error": "Errore nella lettura dei compiti: {}"
    }
}

HISTORY_FILE = "chat_history.json"

# --- 2. Page Configuration ---
st.set_page_config(page_title="Task manager AI Voice Agent", page_icon="🎙️", layout="centered")

# --- 3. Load Credentials ---
load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    st.error("🚫 I couldn't find your GEMINI_API_KEY. Please check your .env file!")
    st.stop()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-flash-latest')

try:
    notion = Client(auth=os.getenv("NOTION_API_KEY"))
    NOTION_DB_ID = os.getenv("NOTION_DB_ID")
except:
    st.error("🚫 I couldn't find your Notion settings. Please check your .env file!")
    st.stop()

# --- 4. Custom Styling ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .user-chat {
        background-color: #2b313e; padding: 15px; border-radius: 15px 15px 0 15px;
        margin: 10px 0; text-align: right; border: 1px solid #29b5e8;
    }
    .ai-chat {
        background-color: #1c1f26; padding: 15px; border-radius: 15px 15px 15px 0;
        margin: 10px 0; text-align: left; border: 1px solid #FF4B4B;
    }
    /* Language dropdown style */
    .stSelectbox label { color: #FF4B4B !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 5. Helper Functions ---

def load_chat_history():
    """Load chat history from local JSON file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading history: {e}")
    return []

def save_chat_history(messages):
    """Save chat history to local JSON file."""
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

async def text_to_speech(text, voice_name):
    """Convert text to speech using the selected voice."""
    communicate = edge_tts.Communicate(text, voice_name)
    await communicate.save("reply.mp3")

def play_audio():
    if os.path.exists("reply.mp3"):
        st.audio("reply.mp3", format="audio/mp3", autoplay=True)

def audio_to_text(audio_segment, lang_code):
    """Convert audio to text using the specified language code."""
    r = sr.Recognizer()
    audio_segment.export("temp.wav", format="wav")
    try:
        with sr.AudioFile("temp.wav") as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data, language=lang_code)
            return text
    except:
        return None

def add_task_to_notion(task_name, deadline=None, lang="English"):
    t = TRANSLATIONS.get(lang, TRANSLATIONS["English"])
    try:
        properties = {
            "Name": {"title": [{"text": {"content": task_name}}]},
            "Status": {"select": {"name": "To DO"}}
        }
        if deadline:
             properties["Deadline"] = {"email": deadline}

        notion.pages.create(parent={"database_id": NOTION_DB_ID}, properties=properties)
        return True, t["added"]
    except Exception as e:
        return False, t["save_error"].format(e)

def find_task(query):
    """Search for a page in the Notion DB."""
    try:
        response = notion.search(query=query, filter={"property": "object", "value": "page"})
        results = response.get("results", [])
        for page in results:
            if page["parent"].get("database_id", "").replace("-", "") == NOTION_DB_ID.replace("-", ""):
                return page
        return results[0] if results else None
    except:
        return None

def get_tasks(time_filter="all", lang="English"):
    """Fetch tasks from Notion based on time filter."""
    t = TRANSLATIONS.get(lang, TRANSLATIONS["English"])
    try:
        filter_params = {"property": "Status", "select": {"does_not_equal": "Done"}}
        # Note: Notion API filtering by date on 'email' property type is tricky/impossible directly.
        # We will fetch all active tasks and filter in Python since 'Deadline' is a string(email).
        
        query_payload = {
            "database_id": NOTION_DB_ID,
            "filter": {
                "and": [
                    {"property": "Status", "select": {"does_not_equal": "Done"}}
                ]
            }
        }
        
        response = notion.databases.query(**query_payload)
        results = response.get("results", [])
        
        filtered_tasks = []
        today = date.today()
        
        for page in results:
            props = page["properties"]
            name = props["Name"]["title"][0]["text"]["content"] if props["Name"]["title"] else "Untitled"
            deadline_str = props.get("Deadline", {}).get("email")
            
            include_task = False
            
            if time_filter == "all":
                include_task = True
            elif deadline_str:
                try:
                    task_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
                    if time_filter == "today" and task_date == today:
                        include_task = True
                    elif time_filter == "tomorrow" and task_date == today + timedelta(days=1):
                        include_task = True
                    elif time_filter == "week" and today <= task_date <= today + timedelta(days=7):
                        include_task = True
                    elif time_filter == "overdue" and task_date < today:
                        include_task = True
                except:
                    # If date parsing fails, ignore or include based on logic
                    pass
            
            if include_task:
                display_date = f" ({deadline_str})" if deadline_str else ""
                filtered_tasks.append(f"- {name}{display_date}")
                
        if not filtered_tasks:
            return True, t["no_tasks"]
            
        return True, f"{t['tasks_header']}\n" + "\n".join(filtered_tasks)
        
    except Exception as e:
        return False, t["read_error"].format(e)

def update_task(task_name, new_status=None, new_deadline=None, lang="English"):
    t = TRANSLATIONS.get(lang, TRANSLATIONS["English"])
    page = find_task(task_name)
    if not page:
        return False, t["not_found"].format(task_name)
    
    props = {}
    if new_status:
        s = new_status.lower()
        if "done" in s or "complete" in s: final_s = "Done"
        elif "progress" in s or "doing" in s: final_s = "In progress"
        else: final_s = "To DO"
        props["Status"] = {"select": {"name": final_s}}
        
    if new_deadline:
        props["Deadline"] = {"email": new_deadline}
        
    try:
        notion.pages.update(page_id=page["id"], properties=props)
        title = page["properties"]["Name"]["title"][0]["text"]["content"]
        return True, t["updated"].format(title)
    except Exception as e:
        return False, t["update_error"].format(e)

def delete_task(task_name, lang="English"):
    t = TRANSLATIONS.get(lang, TRANSLATIONS["English"])
    page = find_task(task_name)
    if not page:
        return False, t["not_found"].format(task_name)
    try:
        notion.pages.update(page_id=page["id"], archived=True)
        title = page["properties"]["Name"]["title"][0]["text"]["content"]
        return True, t["deleted"].format(title)
    except Exception as e:
        return False, t["delete_error"].format(e)

def process_command(text, lang_name):
    """The Brain: Decides what the user wants."""
    t = TRANSLATIONS.get(lang_name, TRANSLATIONS["English"])
    
    import time
    
    system_prompt = f"""
    You are a friendly and helpful assistant fluent in Persian, English, and Italian.
    The user is speaking in **{lang_name}**.
    current_date: {date.today()}
    
    Your goal is to sound natural, warm, and human-like.
    
    Analyze the input and return ONLY a JSON object.
    
    Actions:
    1. "create_task": Add a new task.
    2. "update_task": Change status or deadline.
    3. "delete_task": Remove/Archive a task.
    4. "read_tasks": Query existing tasks (e.g., "What do I have today?", "Show my tasks").
    5. "chat": General conversation.
    
    Output JSON Schema:
    {{
        "action": "create_task" | "update_task" | "delete_task" | "read_tasks" | "chat",
        "task": "Task Name",
        "status": "New Status",
        "deadline": "YYYY-MM-DD",
        "time_filter": "today" | "tomorrow" | "week" | "overdue" | "all" (for read_tasks),
        "reply": "Friendly response in {lang_name}"
    }}
    
    User Input: {text}
    """
    
    # Retry mechanism for 429/Quota errors
    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(system_prompt)
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_text)
            return data, None
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Quota" in error_str or "Resource" in error_str:
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (attempt + 1))
                    continue
                else:
                    return None, t["rate_limit"]
            print(f"Error in process_command: {e}")
            return None, t["generic_error"].format(e)

# --- 6. User Interface ---

st.title("Task manager AI Voice Agent")

# Language Selection
selected_lang_label = st.selectbox(
    "Choose your language:",
    options=list(LANG_CONFIG.keys())
)

# Get current configuration
current_config = LANG_CONFIG[selected_lang_label]

# Load Chat History
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

# Display Chat History
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f'<div class="user-chat">👤 {message["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ai-chat">🤖 {message["content"]}</div>', unsafe_allow_html=True)

st.markdown("---")
st.write(f"👇 Go ahead, I'm listening in **{current_config['sys_prompt']}**:")

# Recording Button
recorder_style = {
    "backgroundColor": "#1c1f26",
    "color": "#FAFAFA",
    "border": "2px solid #FF4B4B",
    "borderRadius": "5px",
    "padding": "15px",
    "fontWeight": "bold",
    "fontSize": "16px"
}

audio = audiorecorder(
    start_prompt="Record", 
    stop_prompt="🔴 Recording...", 
    custom_style=recorder_style,
    show_visualizer=True
)

if len(audio) > 0:
    if "last_audio" not in st.session_state or st.session_state.last_audio != audio:
        st.session_state.last_audio = audio
        
        # 1. Listening phase
        with st.spinner(TRANSLATIONS[current_config['sys_prompt']]["listening"]):
            user_text = audio_to_text(audio, current_config['code'])
        
        if user_text:
            st.session_state.messages.append({"role": "user", "content": user_text})
            save_chat_history(st.session_state.messages) # Save user message
            
            # 2. Thinking phase
            with st.spinner(TRANSLATIONS[current_config['sys_prompt']]["thinking"]):
                ai_data, error_msg = process_command(user_text, current_config['sys_prompt'])
                
                final_reply = ""
                
                if error_msg:
                    final_reply = error_msg
                else:
                    final_reply = ai_data.get("reply", "Done.")
                    
                    action = ai_data.get("action")
                    task_name = ai_data.get("task")
                    lang_key = current_config['sys_prompt']
                    
                    if action == "create_task":
                        success, msg = add_task_to_notion(task_name, ai_data.get("deadline"), lang_key)
                    elif action == "update_task":
                        success, msg = update_task(task_name, ai_data.get("status"), ai_data.get("deadline"), lang_key)
                    elif action == "delete_task":
                        success, msg = delete_task(task_name, lang_key)
                    elif action == "read_tasks":
                        success, msg = get_tasks(ai_data.get("time_filter", "all"), lang_key)
                        if success:
                            final_reply += f"\n\n{msg}"
                        else:
                            final_reply += f"\n\n❌ {msg}"
                        success = True # Don't prepend checklist icon for read output
                    else:
                        success = True
                        msg = ""
                        
                    if action in ["create_task", "update_task", "delete_task"]:
                        if success:
                            final_reply = f"✅ {final_reply}"
                        else:
                            final_reply = f"❌ {msg}"

            st.session_state.messages.append({"role": "assistant", "content": final_reply})
            save_chat_history(st.session_state.messages) # Save AI response
            
            # 3. Speaking phase
            asyncio.run(text_to_speech(final_reply, current_config['voice']))
            play_audio()
            
            st.rerun()
        else:
            st.warning(TRANSLATIONS[current_config['sys_prompt']]["retry"])