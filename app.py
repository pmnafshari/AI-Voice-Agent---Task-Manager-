
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
import uuid
import logging
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
model = genai.GenerativeModel('gemini-2.0-flash-lite')

try:
    if not os.getenv("NOTION_API_KEY"):
        st.error("NOTION_API_KEY is not set in .env file")
        st.stop()
        
    notion = Client(auth=os.getenv("NOTION_API_KEY"))
    
    # helper to format UUID
    def format_uuid(id_str):
        try:
            return str(uuid.UUID(id_str))
        except ValueError:
            return id_str

    raw_db_id = os.getenv("NOTION_DB_ID", "")
    NOTION_DB_ID = format_uuid(raw_db_id)
    
    if not NOTION_DB_ID:
         st.warning("NOTION_DB_ID is not set in .env")

except Exception as e:
    st.error(f"Error initializing Notion client: {e}")
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
        margin: 10px 0; text-align: left; border: 1px solid #4CAF50;
    }
    .ai-chat-error {
        background-color: #261c1c; padding: 15px; border-radius: 15px 15px 15px 0;
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
            "filter": {
                "and": [
                    {"property": "Status", "select": {"does_not_equal": "Done"}}
                ]
            }
        }
        
        # response = notion.request(
        #     path=f"databases/{NOTION_DB_ID}/query",
        #     method="POST",
        #     body=query_payload
        # )
        
        headers = {
            "Authorization": f"Bearer {os.getenv('NOTION_API_KEY')}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        res = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
            json=query_payload,
            headers=headers
        )
        if res.status_code != 200:
             raise Exception(f"Notion API Error: {res.text}")
             
        response = res.json()
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
    2. "update_task": Change status or deadline. ONLY if user explicitly names a task to update.
    3. "delete_task": Remove/Archive a task. ONLY if user explicitly names a task.
    4. "read_tasks": Query existing tasks (e.g., "What do I have today?", "Show my tasks").
    5. "chat": General conversation, OR if the input is unclear/ambiguous.
    
    IMPORTANT: 
    - Do NOT guess a task name if the user didn't say one. 
    - If the input is just one word like "valid", "test", or "hello", treat it as "chat" and ask for clarification.
    - Do NOT return "update_task" unless a specific task name is mentioned.
    
    Output JSON Schema:
    {{
        "action": "create_task" | "update_task" | "delete_task" | "read_tasks" | "chat",
        "task": "Task Name (Required for create/update/delete)",
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

# Sidebar for History & New Chat
with st.sidebar:
    st.header("💬 Chat History")
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.current_chat_id = str(uuid.uuid4())
        save_chat_history([]) # Save empty to init file
        st.rerun()
    
    st.markdown("---")
    
    
    # List history files
    history_dir = "history"
    if not os.path.exists(history_dir):
        os.makedirs(history_dir)
    
    # Rename current chat
    if "current_chat_id" in st.session_state:
        current_name = st.session_state.current_chat_id
        new_name = st.text_input("🖊️ Rename Chat", value=current_name)
        if new_name != current_name:
            if new_name and not os.path.exists(os.path.join(history_dir, f"{new_name}.json")):
                try:
                    os.rename(
                        os.path.join(history_dir, f"{current_name}.json"),
                        os.path.join(history_dir, f"{new_name}.json")
                    )
                    st.session_state.current_chat_id = new_name
                    st.rerun()
                except Exception as e:
                    st.error(f"Error renaming: {e}")
            elif os.path.exists(os.path.join(history_dir, f"{new_name}.json")):
                st.warning("A chat with this name already exists.")

    st.markdown("---")
    
    files = [f for f in os.listdir(history_dir) if f.endswith(".json")]
    # Sort by modification time (newest first)
    files.sort(key=lambda x: os.path.getmtime(os.path.join(history_dir, x)), reverse=True)
    
    for filename in files:
        name = filename.replace('.json', '')
        file_path = os.path.join(history_dir, filename)
        
        # Highlight current chat
        label = f"🟢 {name}" if name == st.session_state.get("current_chat_id") else f"📄 {name}"
        
        if st.button(label, key=filename, use_container_width=True):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    st.session_state.messages = json.load(f)
                    st.session_state.current_chat_id = name
                    st.rerun()
            except Exception as e:
                st.error(f"Error loading {filename}: {e}")

# Language Selection (Default to English - Index 1)
# Keys: ["Persian 🇮🇷", "English 🇺🇸", "Italian 🇮🇹"]
selected_lang_label = st.selectbox(
    "Choose your language:",
    options=list(LANG_CONFIG.keys()),
    index=1
)

# Get current configuration
current_config = LANG_CONFIG[selected_lang_label]

# Initialize Session
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# Helper to save CURRENT chat
def save_current_chat():
    file_path = os.path.join("history", f"{st.session_state.current_chat_id}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

# Overwrite the old save_chat_history to point to new logic or just use save_current_chat
def save_chat_history(msg):
    # Backward compatibility shim
    save_current_chat()

# Display Chat History In Scrollable Container
chat_container = st.container(height=400)
with chat_container:
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f'<div class="user-chat">👤 {message["content"]}</div>', unsafe_allow_html=True)
        else:
            # Check for error indicators in content
            content = message["content"]
            style_class = "ai-chat"
            # Known error prefixes from TRANSLATIONS or typical error emojis
            if "⚠️" in content or "❌" in content or "Oops" in content or "Error" in content or "🚫" in content:
                style_class = "ai-chat-error"
                
            st.markdown(f'<div class="{style_class}">🤖 {content}</div>', unsafe_allow_html=True)
            
    # Auto-scroll to bottom using JavaScript
    st.components.v1.html(
        """
        <script>
            function scrollToBottom() {
                // Target Streamlit's specific scrollable container structure
                var scrollableElements = window.parent.document.querySelectorAll('.st-emotion-cache-1y4p8pa, [data-testid="stVerticalBlockBorderWrapper"] > div');
                
                scrollableElements.forEach(function(element) {
                    element.scrollTop = element.scrollHeight;
                });
                
                // Fallback: finding any div with significant overflow
                var allDivs = window.parent.document.getElementsByTagName("div");
                for (var i = 0; i < allDivs.length; i++) {
                    var div = allDivs[i];
                    if (getComputedStyle(div).overflowY === "auto" || getComputedStyle(div).overflowY === "scroll") {
                        div.scrollTop = div.scrollHeight;
                    }
                }
            }
            // Run immediately and after a slight delay to ensure rendering
            scrollToBottom();
            setTimeout(scrollToBottom, 100);
            setTimeout(scrollToBottom, 500);
        </script>
        """,
        height=0,
        width=0,
    )

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
    show_visualizer=False
)

if len(audio) > 0:
    if "last_audio" not in st.session_state or st.session_state.last_audio != audio:
        st.session_state.last_audio = audio
        
        # 1. Listening phase
        with st.spinner(TRANSLATIONS[current_config['sys_prompt']]["listening"]):
            user_text = audio_to_text(audio, current_config['code'])
        
        if user_text:
            # Auto-renaming for new chats
            if len(st.session_state.messages) == 0:
                # Generate a safe filename from the first few words
                safe_name = "".join([c for c in user_text[:30] if c.isalnum() or c in " -_"]).strip()
                if not safe_name: safe_name = "New Chat"
                
                # Check for duplicate
                base_name = safe_name
                counter = 1
                while os.path.exists(os.path.join("history", f"{safe_name}.json")):
                    safe_name = f"{base_name} ({counter})"
                    counter += 1
                
                # Rename the file if it exists (it shouldn't for a new chat usually, but good practice)
                # Or just update the ID so the NEXT save uses the new name
                
                # If we're on a UUID, we can just switch to the new name
                # If a file already existed for the UUID (e.g. empty init), rename it
                old_id = st.session_state.current_chat_id
                st.session_state.current_chat_id = safe_name
                
                old_path = os.path.join("history", f"{old_id}.json")
                if os.path.exists(old_path):
                    os.rename(old_path, os.path.join("history", f"{safe_name}.json"))
            
            st.session_state.messages.append({"role": "user", "content": user_text})
            save_current_chat() # Save user message
            
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
            save_current_chat() # Save AI response
            
            # 3. Speaking phase
            # Generate audio and store in session state
            asyncio.run(text_to_speech(final_reply, current_config['voice']))
            
            if os.path.exists("reply.mp3"):
                with open("reply.mp3", "rb") as f:
                    st.session_state.audio_bytes = f.read()
            
            st.rerun()
        else:
            st.warning(TRANSLATIONS[current_config['sys_prompt']]["retry"])

    import base64
    
    # Play audio if it exists in session state
    if "audio_bytes" in st.session_state and st.session_state.audio_bytes:
        # st.audio(st.session_state.audio_bytes, format="audio/mp3", autoplay=True)
        
        # Use HTML/JS to play audio without showing the player
        b64 = base64.b64encode(st.session_state.audio_bytes).decode()
        md = f"""
            <audio autoplay style="display:none;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md, unsafe_allow_html=True)
        
        # Clear it so it doesn't replay on next manual refresh
        del st.session_state.audio_bytes