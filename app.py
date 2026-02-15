
import streamlit as st
import speech_recognition as sr
import google.generativeai as genai
import os
import json
import asyncio
import edge_tts
from dotenv import load_dotenv
from audiorecorder import audiorecorder
from notion_client import Client

# --- 1. Language & Voice Settings ---
# Configuration for each language
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
        margin: 10px 0; text-align: right; border: 1px solid #3d4450;
    }
    .ai-chat {
        background-color: #1c1f26; padding: 15px; border-radius: 15px 15px 15px 0;
        margin: 10px 0; text-align: left; border: 1px solid #FF4B4B;
    }
    .stAudioRecorder { display: flex; justify-content: center; }
    /* Language dropdown style */
    .stSelectbox label { color: #FF4B4B !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 5. Core Functions (Multi-language) ---

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
            # Recognize speech using the dynamic language code
            text = r.recognize_google(audio_data, language=lang_code)
            return text
    except:
        return None

def add_task_to_notion(task_name, deadline=None):
    try:
        properties = {
            "Name": {"title": [{"text": {"content": task_name}}]},
            "Status": {"select": {"name": "To DO"}}
        }
        if deadline:
             # Workaround: 'Deadline' property is type 'email', so we save the date as a string.
             properties["Deadline"] = {"email": deadline}

        notion.pages.create(parent={"database_id": NOTION_DB_ID}, properties=properties)
        return True, "I've added that to your list."
    except Exception as e:
        return False, f"I couldn't save that to Notion. Error: {e}"

def find_task(query):
    """Search for a page in the Notion DB."""
    try:
        response = notion.search(query=query, filter={"property": "object", "value": "page"})
        results = response.get("results", [])
        # Ideally check if parent.database_id matches NOTION_DB_ID
        for page in results:
            if page["parent"].get("database_id", "").replace("-", "") == NOTION_DB_ID.replace("-", ""):
                return page
        return results[0] if results else None
    except:
        return None

def update_task(task_name, new_status=None, new_deadline=None):
    page = find_task(task_name)
    if not page:
        return False, f"I couldn't find any task matching '{task_name}'."
    
    props = {}
    if new_status:
        # Standardize status (assuming 'To DO', 'In progress', 'Done' exist in Notion)
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
        return True, f"Updated '{title}'."
    except Exception as e:
        return False, f"Update Error: {e}"

def delete_task(task_name):
    page = find_task(task_name)
    if not page:
        return False, f"I couldn't find task '{task_name}'."
    try:
        notion.pages.update(page_id=page["id"], archived=True)
        title = page["properties"]["Name"]["title"][0]["text"]["content"]
        return True, f"Deleted '{title}'."
    except Exception as e:
        return False, f"Delete Error: {e}"

def process_command(text, lang_name):
    """The Brain: Decides what the user wants."""
    
    # System Prompt with a more human/conversational persona
    system_prompt = f"""
    You are a friendly and helpful assistant fluent in Persian, English, and Italian.
    The user is speaking in **{lang_name}**.
    
    Your goal is to sound natural, warm, and human-like.
    
    Analyze the input and return ONLY a JSON object.
    
    Actions:
    1. "create_task": Add a new task.
    2. "update_task": Change status (e.g. done, doing) or deadline.
    3. "delete_task": Remove/Archive a task.
    4. "chat": General conversation.
    
    Output JSON Schema:
    {{
        "action": "create_task" | "update_task" | "delete_task" | "chat",
        "task": "Task Name (for create/update/delete)",
        "status": "New Status (e.g. 'Done', 'In progress', 'To DO') - optional for update",
        "deadline": "YYYY-MM-DD - optional for create/update",
        "reply": "Friendly response in {lang_name}"
    }}
    
    User Input: {text}
    """
    
    try:
        response = model.generate_content(system_prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_text)
        return data, None
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "Quota" in error_str:
            return None, "⚠️ I'm a bit overwhelmed right now (Rate Limit). Give me a minute to catch my breath!"
        print(f"Error in process_command: {e}")
        return None, f"Oops, something went wrong: {e}"

# --- 6. User Interface ---

st.title("Task manager AI Voice Agent")

# Language Selection
selected_lang_label = st.selectbox(
    "Choose your language:",
    options=list(LANG_CONFIG.keys())
)

# Get current configuration
current_config = LANG_CONFIG[selected_lang_label]

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat History
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f'<div class="user-chat">👤 {message["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ai-chat">🤖 {message["content"]}</div>', unsafe_allow_html=True)

st.markdown("---")
st.write(f"👇 Go ahead, I'm listening in **{current_config['sys_prompt']}**:")

# Recording Button
audio = audiorecorder("⏺️ Talk", "⏹️ Done")

if len(audio) > 0:
    if "last_audio" not in st.session_state or st.session_state.last_audio != audio:
        st.session_state.last_audio = audio
        
        # 1. Listening phase
        with st.spinner(f"🎧 I'm all ears..."):
            user_text = audio_to_text(audio, current_config['code'])
        
        if user_text:
            st.session_state.messages.append({"role": "user", "content": user_text})
            
            # 2. Thinking phase
            with st.spinner("🧠 Let me think about that..."):
                ai_data, error_msg = process_command(user_text, current_config['sys_prompt'])
                
                final_reply = ""
                
                if error_msg:
                    final_reply = error_msg
                else:
                    final_reply = ai_data.get("reply", "Done.")
                    
                    action = ai_data.get("action")
                    task_name = ai_data.get("task")
                    
                    if action == "create_task":
                        success, msg = add_task_to_notion(task_name, ai_data.get("deadline"))
                    elif action == "update_task":
                        success, msg = update_task(task_name, ai_data.get("status"), ai_data.get("deadline"))
                    elif action == "delete_task":
                        success, msg = delete_task(task_name)
                    else:
                        success = True
                        msg = ""
                        
                    if action in ["create_task", "update_task", "delete_task"]:
                        if success:
                            final_reply = f"✅ {final_reply}"
                        else:
                            final_reply = f"❌ {msg}"

            st.session_state.messages.append({"role": "assistant", "content": final_reply})
            
            # 3. Speaking phase
            asyncio.run(text_to_speech(final_reply, current_config['voice']))
            play_audio()
            
            st.rerun()
        else:
            st.warning("Sorry, I didn't catch that. Could you please repeat?")