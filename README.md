# Task Manager AI Voice Agent

This project is a voice-controlled assistant that helps you manage your daily tasks. It connects to your Notion database to read, add, update, and delete tasks just by talking to it. The assistant uses Google Gemini for understanding what you say and speaks back to you in a natural voice.

## Features
It can handle several actions through voice commands:
*   Add new tasks to your Notion list.
*   Update the status or deadline of existing tasks.
*   Delete or archive tasks you no longer need.
*   Read your tasks for today, tomorrow, or the whole week.
*   Support for English, Persian, and Italian languages.
*   Save your conversation history so you can see past chats.

## Libraries and Tools Used
This project relies on these main components:
*   **Streamlit**: Builds the web interface that you interact with.
*   **Google Gemini (via google-genai)**: The AI brain that understands your requests.
*   **Notion Client**: Connects to your Notion workspace to manage data.
*   **SpeechRecognition**: Converts your voice into text.
*   **Edge-TTS**: Converts text back into speech for the assistant.
*   **Streamlit-Audiorecorder**: recording audio in the browser.

## File Descriptions
Here is a quick look at what each file does:
*   **app.py**: The main file that runs the entire application.
*   **requirements.txt**: A list of all the Python libraries you need to install.
*   **.env**: A secret file where you store your API keys (not included in the code).
*   **history/**: A folder where your chat conversations are saved automatically.

## How to Set It Up
Follow these steps to get the project running on your computer.

### 1. Get the Code
First, you need to download this project. You can clone it using git:
```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2. Install Python Components
Make sure you have Python installed. Then, create a virtual environment to keep things clean:
```bash
python -m venv venv
```

Activate the virtual environment:
*   **Windows**: `venv\Scripts\activate`
*   **Mac/Linux**: `source venv/bin/activate`

Now, install the required libraries:
```bash
pip install -r requirements.txt
```

### 3. Set Up Your Keys
Create a new file named `.env` in the main folder. You will need to add your personal keys here. Open it with a text editor and add these three lines:

```
GEMINI_API_KEY=your_google_gemini_key
NOTION_API_KEY=your_notion_integration_token
NOTION_DB_ID=your_notion_database_id
```

**Where to find these:**
*   **Gemini Key**: Get it from Google AI Studio.
*   **Notion Key**: Create a new integration at notion.com/my-integrations.
*   **Notion DB ID**: Open your Notion database as a full page. The ID is the long string of characters in the URL after your workspace name.

*Important*: Make sure to share your Notion database with the integration you created (click the three dots > Connections > Add connections).

### 4. Run the App
Once everything is installed and configured, run this command in your terminal:
```bash
streamlit run app.py
```
The application will open automatically in your web browser. You can now choose your language and start speaking to your assistant.
