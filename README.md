# Bloggers — AI Content Management & Publishing Studio for Windows

**Bloggers** is a production-quality Windows desktop application designed for high-integrity, research-backed blogging with Google Blogger integration. Built with Electron and FastAPI, and powered exclusively by the official **Google GenAI SDK** using Gemini API and the **Nano Banana** featured image generation model.

> **Publication Managed**: ByteBlooming Tech Journal
> **Application Name**: Bloggers
> **Installer Package**: `dist/Bloggers-Setup-1.0.0.exe`

---

## Key Features

- **Native Windows Desktop Experience (Electron)**:
  - Frameless-ready responsive desktop window with custom branding and icons.
  - Automatically manages and spawns the local Python/FastAPI backend on startup and cleans up gracefully upon exit.
  - Local SQLite persistence with zero telemetry or cloud lock-in.
- **Topic-Driven Web Image Search & Attribution**:
  - Replaced AI image generation with a multi-query web image search architecture (Wikimedia Commons, Openverse, and verified public domain archives).
  - Relevance score gate (Strict 70, Balanced 50, Relaxed 35) with universal negative exclusion filters to prevent unrelated stock pictures.
  - Full author attribution, source URL, licensing info, and custom hero poster upload with size/resolution security gates.
- **Internet-Powered Topic Discovery**:
  - Real Google Trends Trending Now RSS (India default + configurable countries) and category-specific Google News search feeds.
  - Transparent labeling: never confuses offline fallback suggestions with verified live trends.
  - Evergreen and random topic brainstorms with difficulty estimation and fuzzy deduplication.
- **Editorial Publication Preview & WYSIWYG Studio**:
  - Full reading experience: desktop reading column (`max-width: 760px`) and realistic mobile smartphone preview.
  - Bleach-powered HTML sanitization with strict allowlist tailored for Blogger posts.
  - Notion-style formatting toolbar with docked AI writing copilot (Regenerate Section, Fact-Check Selection, Polish Flow, Expand, Shorten).
- **Security & Safety Hardening**:
  - Restricts CORS to verified local loopback origins (`127.0.0.1`, `localhost`).
  - Active `.env` file excluded from packaged desktop application distributions.
  - Validated article status state transitions preventing direct approval bypass.
  - Image upload size (15MB) and decompression bomb protection (8000x8000 max).
- **Safe Blogger Integration**:
  - Connects via official Google OAuth 2.0 and Blogger API v3.
  - Creates **Blogger Drafts** (`isDraft=True`) by default; never silently auto-publishes without explicit user confirmation.
- **Zero-Credential Demo Mode**:
  - Test all UI features, topic discovery, drafting, and quality score breakdowns immediately without API keys.
- **Secret Isolation**:
  - API keys and OAuth secrets are masked in memory and never exposed to client-side code, logs, or UI elements.

---

## Architecture & Workflow

```
[ Topic Idea ]
      │
      ▼
[ Research Analyst ] ──► Stores verified sources & facts
      │
      ▼
[ Article Writer ] ──► Structures full people-first draft
      │
      ▼
[ Fact Checker ] ──► Verifies claims vs authoritative sources
      │
      ▼
[ SEO & Originality Reviewers ] ──► Optimizes metadata & checks freshness
      │
      ▼
[ Quality Reviewer (0-100 Gate) ] ── (If score < threshold) ──► [ Final Editor Revision ]
      │
      ▼ (If passed)
[ Ready for Human Approval ]
      │
 ┌────┴────────────────────────┬──────────────────────┐
 │                             │                      │
 ▼                             ▼                      ▼
[ User Approves ]    [ User Requests Revision ]    [ User Rejects ]
 │
 ▼
[ Blogger API v3 Draft Created (isDraft=True) ]
```

---

## Setup & Installation

### 1. Installing Python
Download and install **Python 3.12 or newer** (tested on Python 3.12, 3.13, and 3.14) from [python.org](https://www.python.org/downloads/).
- **Important on Windows**: During installation, check the box **"Add python.exe to PATH"**.

### 2. Creating the Virtual Environment
Open PowerShell or Command Prompt in the project folder (`c:\Users\HP\Pictures\Blogger agent`):
```powershell
python -m venv venv
```

### 3. Installing Dependencies
Activate the virtual environment and install the required packages:
```powershell
.\venv\Scripts\pip install -r requirements.txt
```

### 4. Creating `.env`
Copy `.env.example` to create your active `.env` configuration file:
```powershell
copy .env.example .env
```

### 5. Adding Gemini API Key
1. Obtain a free Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Open `.env` and set your key:
   ```env
   GEMINI_API_KEY=AIzaSy...your_real_key_here...
   GEMINI_MODEL=gemini-3.8-flash
   DEMO_MODE=false
   ```
*(Leave `DEMO_MODE=true` if you wish to test the system offline first!)*

### 6. Setting Up Google Cloud / Blogger OAuth 2.0
To push drafts directly into your Google Blogger account:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `Blogger-AI-Agent`).
3. Under **APIs & Services > Library**, search for and enable **Blogger API v3**.
4. Under **APIs & Services > OAuth consent screen**:
   - Choose **External**.
   - Fill in an App name and your support email.
   - Under **Scopes**, add `https://www.googleapis.com/auth/blogger`.
   - Add your Gmail as a **Test User**.
5. Under **APIs & Services > Credentials**:
   - Click **Create Credentials > OAuth client ID**.
   - Select **Web application**.
   - Under **Authorized redirect URIs**, add:
     `http://localhost:8000/api/blogger/oauth2callback`
6. Copy your Client ID and Client Secret into `.env`:
   ```env
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/blogger/oauth2callback
   BLOGGER_BLOG_ID=1234567890123456789
   ```

### 7. Running the Application

#### Option A: 1-Click Windows Desktop Launcher (Recommended)
Double-click `run-desktop.bat` or run:
```bat
run-desktop.bat
```
This automatically verifies Python, sets up `venv`, installs required dependencies, and boots the native **Bloggers** desktop app with the auto-managed backend!

#### Option B: Electron Development Mode
```powershell
npm run dev
# or
npm start
```

#### Option C: Web Browser Mode
```bat
run.bat
```
Or directly from PowerShell:
```powershell
.\venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Open your browser to: **`http://127.0.0.1:8000`**

---

## Building & Packaging the Windows Executable

To compile a distributable Windows Installer (`.exe`) or standalone directory:

```powershell
# 1. Unpacked standalone directory (dist/win-unpacked/Bloggers.exe)
npm run build

# 2. Windows NSIS Installer (dist/Bloggers-Setup-1.0.0.exe)
npm run dist

# 3. Portable single executable
npm run pack
```

The output installer is located at:
`dist/Bloggers-Setup-1.0.0.exe` (NSIS installer with desktop & start menu shortcuts).

---

## User Guide

### 8. Using Demo Mode (Offline / Zero-Credential)
If you don't have API keys yet, Blogger AI Agent includes a **Demo Mode**:
- Open the application at `http://127.0.0.1:8000`.
- In the top bar, you will see the yellow **Demo Mode Active** badge.
- You can test topic seeding, research collection, drafting, quality score breakdown, and simulated Blogger draft creation with zero API costs.

### 9. Creating Your First Article
1. Go to the **Topics** tab.
2. Click **⚡ Seed Demo Topic** or **+ New Topic** to enter:
   - Topic headline
   - Target audience
   - Search intent (Informational, Commercial, Navigational, Transactional)
   - Target length (Short ~800w, Medium ~1500w, Long ~2500w)
   - Keywords
3. Click **Generate Draft** (or use **🚀 Start New Pipeline** in the Articles tab).
4. The orchestrator will run the autonomous multi-agent pipeline and present the resulting draft.

### 10. Approving an Article
1. Switch to the **Quality & Approval** tab.
2. Review the **Overall Quality Score** (and the 7 dimension meters).
3. Inspect the **Fact-Checking Verification Claims** table:
   - Claims are marked `SUPPORTED` (green), `UNCERTAIN` (amber), or `UNSUPPORTED` (red).
4. Read the article content and SEO metadata.
5. If satisfied, click **✓ Approve (Push Blogger Draft)**.

### 11. Creating a Blogger Draft
- Once an article with a score above the quality threshold (`>= 85/100`) is approved, Blogger AI Agent immediately calls the Blogger API v3 with `isDraft=True`.
- A direct link to edit the draft in your Google Blogger dashboard will appear in the UI.

### 12. Enabling Publishing Later (Guarded)
By design, **publishing live content is disabled by default**:
- `AUTO_PUBLISH=false`
Even if `AUTO_PUBLISH=true` is set later, articles must:
1. Pass the strict Quality Gate threshold (`>= 85/100`).
2. Have zero critical unsupported factual claims.
3. Require explicit human confirmation (`confirm_publish=True`).

### 13. Security & Privacy Precautions
- **No Secret Leakage**: The backend masks API keys in memory (`AIza...89`), sanitizes all logs, and never exposes tokens in HTTP endpoints.
- **Local Storage**: All articles, research notes, and revisions are stored locally in SQLite (`data/blogger_agent.db`).
- **No Local LLMs**: Preserves your 8 GB RAM and keeps system responsive.

---

## Running Automated Tests

Run the complete test suite with pytest:
```powershell
.\venv\Scripts\pytest -v
```
The test suite covers:
- Configuration and secret masking (`test_config.py`)
- SQLite database relationships and cascading (`test_database.py`)
- Article state transitions & orchestrator workflow (`test_article_workflow.py`)
- Quality gate & factual accuracy enforcement (`test_quality_gate.py`)
- Blogger API v3 draft creation & OAuth flow (`test_blogger_service.py`)
- Gemini token usage tracker & retry mechanism (`test_gemini_service.py`)
- Absolute secret protection in API responses (`test_secret_protection.py`)
