# Echo Beta 1

Echo Beta 1 is a desktop Python assistant prototype. It is a first milestone for the larger Echo project, not the finished long-term system.

## Included
- Tkinter chat interface
- Recent conversation history stored locally
- Local notes
- Restricted arithmetic calculator
- Study-plan helper
- Optional real language-model connection through an OpenAI-compatible Chat Completions API
- Offline fallback commands when no API key is configured

## Requirements
- Python 3.10 or newer
- Tkinter (included with most standard Python installations)
- Internet connection and a valid provider API key only for connected AI chat

## Run
1. Install Python 3.10+ from https://www.python.org/downloads/
2. Extract the project folder.
3. Open a terminal in this folder.
4. Run:

   `python echo_beta1.py`

On some systems, use `python3 echo_beta1.py`.

## Enable real AI chat
Set environment variables before starting Echo:

**Windows PowerShell**
```powershell
$env:ECHO_API_KEY="your_api_key_here"
$env:ECHO_API_URL="https://api.openai.com/v1/chat/completions"
$env:ECHO_MODEL="gpt-4o-mini"
python echo_beta1.py
```

**macOS / Linux**
```bash
export ECHO_API_KEY="your_api_key_here"
export ECHO_API_URL="https://api.openai.com/v1/chat/completions"
export ECHO_MODEL="gpt-4o-mini"
python3 echo_beta1.py
```

Use a model and endpoint supported by your API provider. API usage may cost money. Do not share your key or put it in the source code. If no key is configured, Echo uses limited offline tools rather than pretending to be a full AI model.

## Offline commands
- `/help`
- `/calc 12 * (4 + 3)`
- `/study Geometry: parallel lines`
- `/summarize Paste text here`

## Local data
Echo saves history and notes in `~/.echo_beta1/`:
- `history.json`
- `notes.json`

These files are stored on the current computer. Do not save sensitive information in the prototype.

## Known limitations
- No built-in web search, voice input, image understanding, or agent execution yet.
- API compatibility depends on the selected provider.
- Chat history currently saves a new snapshot after each assistant reply; rapid repeated chats may create duplicate history entries.
- Offline summarization is basic text extraction, not semantic AI summarization.
- This is a prototype and has not undergone a formal security audit or independent classroom rubric review.

## School demonstration idea
1. Launch Echo and show the interface.
2. Use the calculator.
3. save a short note and reopen Notes.
4. Run `/study` on a current class topic.
5. Explain the difference between offline tools and a connected language model.
