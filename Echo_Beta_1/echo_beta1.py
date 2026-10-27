"""
Echo Beta 1
A small, extensible desktop assistant prototype built with Python's standard library.

Features:
- Desktop chat UI (Tkinter)
- Optional real-model API integration using an OpenAI-compatible chat completions endpoint
- Local fallback helpers when no API key is configured
- Persistent conversation history and notes
- Calculator with a restricted AST evaluator
- Study prompt helper

Security note:
- Set ECHO_API_KEY in your environment; never hard-code secrets in this file.
- The API provider and model can be configured with ECHO_API_URL and ECHO_MODEL.
"""

from __future__ import annotations

import ast
import json
import os
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, ttk

APP_NAME = "ECHO"
VERSION = "Beta 1"
DATA_DIR = Path.home() / ".echo_beta1"
HISTORY_FILE = DATA_DIR / "history.json"
NOTES_FILE = DATA_DIR / "notes.json"

DEFAULT_API_URL = os.getenv(
    "ECHO_API_URL",
    "https://api.openai.com/v1/chat/completions"
)
DEFAULT_MODEL = os.getenv("ECHO_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("ECHO_API_KEY", "").strip()

SYSTEM_PROMPT = (
    "You are Echo, a general-purpose assistant prototype. Be accurate, concise, "
    "and clear. If you are unsure, say so. For schoolwork, explain the reasoning "
    "and help the student learn rather than merely encouraging copying. Do not "
    "claim to have performed actions you did not perform."
)


def safe_calculate(expression: str):
    """Evaluate basic arithmetic without eval() or arbitrary code execution."""
    tree = ast.parse(expression, mode="eval")
    allowed_binops = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
                      ast.Mod, ast.Pow)
    allowed_unary = (ast.UAdd, ast.USub)

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, allowed_binops):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8:
                raise ValueError("Exponent is too large for this calculator.")
            result = {
                ast.Add: lambda: left + right,
                ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right,
                ast.Div: lambda: left / right,
                ast.FloorDiv: lambda: left // right,
                ast.Mod: lambda: left % right,
                ast.Pow: lambda: left ** right,
            }[type(node.op)]()
            if isinstance(result, complex):
                raise ValueError("Complex results are not supported.")
            return result
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, allowed_unary):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        raise ValueError("Use numbers and basic operators only: + - * / // % ** ( ).")

    result = visit(tree)
    if isinstance(result, float) and (result != result or abs(result) == float("inf")):
        raise ValueError("Result is outside the supported range.")
    return result


def load_json(path: Path, fallback):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return fallback


def save_json(path: Path, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def local_reply(text: str) -> str:
    """Predictable offline helpers; not a substitute for a language model."""
    cleaned = text.strip()
    low = cleaned.lower()

    if low.startswith("/calc "):
        try:
            return f"Result: {safe_calculate(cleaned[6:].strip())}"
        except Exception as exc:
            return f"Calculator error: {exc}"

    if low.startswith("/note "):
        return "Use the Notes button to save a note, or type /help to see commands."

    if low in {"/help", "help"}:
        return (
            "Echo Beta 1 offline commands:\n"
            "• /calc 12 * (4 + 3) — calculate an arithmetic expression\n"
            "• /study TOPIC — create a study checklist for a topic\n"
            "• /summarize TEXT — make a short outline from supplied text\n"
            "• /help — show these commands\n\n"
            "For open-ended questions, configure ECHO_API_KEY to connect a language model."
        )

    if low.startswith("/study "):
        topic = cleaned[7:].strip()
        if not topic:
            return "Add a topic after /study."
        return (
            f"Study plan: {topic}\n\n"
            "1. Read or watch one reliable explanation (10–20 minutes).\n"
            "2. Write 5–8 notes in your own words.\n"
            "3. Close the source and recall the main ideas from memory.\n"
            "4. Answer 5 practice questions without looking at your notes.\n"
            "5. Check mistakes and retry the missed questions."
        )

    if low.startswith("/summarize "):
        body = cleaned[11:].strip()
        if not body:
            return "Paste text after /summarize."
        sentences = re.split(r"(?<=[.!?])\s+", body)
        excerpt = " ".join(sentences[:3])
        if len(excerpt) > 700:
            excerpt = excerpt[:697] + "..."
        return (
            "Offline text outline (basic extraction, not AI):\n\n"
            f"{excerpt}\n\n"
            f"Input length: {len(body)} characters. Review the source to verify that "
            "the excerpt preserves the important details."
        )

    if any(greeting in low for greeting in ("hello", "hi echo", "hey echo")):
        return (
            "Echo Beta 1 is online. I can run basic offline tools with /help. "
            "For full conversational answers, configure a language-model API key."
        )

    return (
        "I'm running in offline fallback mode, so I can't reliably answer open-ended "
        "questions yet. Try /help, /calc, /study, or /summarize, or configure "
        "ECHO_API_KEY to enable a real language model."
    )


def call_model(messages: list[dict]) -> str:
    if not API_KEY:
        return local_reply(messages[-1]["content"])
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages[-20:],
        "temperature": 0.4,
    }
    request = urllib.request.Request(
        DEFAULT_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:500]
        return f"Model API error ({exc.code}): {details}"
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return f"Could not reach the model API: {exc}"


class EchoApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} — {VERSION}")
        self.root.geometry("1000x680")
        self.root.minsize(760, 520)
        self.root.configure(bg="#101820")

        self.history = load_json(HISTORY_FILE, [])
        self.notes = load_json(NOTES_FILE, [])
        self.messages: list[dict] = []
        self.busy = False

        self._build_style()
        self._build_ui()
        self._append_message(
            "Echo",
            "System online. Beta 1 is ready.\n"
            + ("Connected mode configured." if API_KEY else
               "Offline fallback mode. Set ECHO_API_KEY for full AI chat.")
        )
        self._render_history()

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", padding=7, font=("Segoe UI", 10))
        style.configure("TLabel", background="#101820", foreground="#e8eef2",
                        font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"),
                        foreground="#8be9fd")
        style.configure("Muted.TLabel", foreground="#9aabb6", font=("Segoe UI", 9))

    def _build_ui(self):
        outer = tk.Frame(self.root, bg="#101820")
        outer.pack(fill="both", expand=True, padx=18, pady=14)

        header = tk.Frame(outer, bg="#101820")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="ECHO", style="Title.TLabel").pack(side="left")
        self.status_var = tk.StringVar(
            value=f"{VERSION}  •  {'Model ready' if API_KEY else 'Offline tools'}"
        )
        ttk.Label(header, textvariable=self.status_var, style="Muted.TLabel").pack(
            side="right", pady=8
        )

        body = tk.Frame(outer, bg="#101820")
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg="#182630", width=205)
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="WORKSPACE", bg="#182630", fg="#8be9fd",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(14, 8))
        ttk.Button(sidebar, text="＋ New chat", command=self.new_chat).pack(
            fill="x", padx=10, pady=4
        )
        ttk.Button(sidebar, text="Save note", command=self.save_note_dialog).pack(
            fill="x", padx=10, pady=4
        )
        ttk.Button(sidebar, text="View notes", command=self.view_notes).pack(
            fill="x", padx=10, pady=4
        )
        ttk.Button(sidebar, text="Calculator", command=self.calculator_dialog).pack(
            fill="x", padx=10, pady=4
        )
        ttk.Button(sidebar, text="Study helper", command=self.study_dialog).pack(
            fill="x", padx=10, pady=4
        )
        ttk.Button(sidebar, text="Clear chat", command=self.clear_chat).pack(
            fill="x", padx=10, pady=4
        )
        tk.Label(sidebar, text="RECENT CHATS", bg="#182630", fg="#8be9fd",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(18, 6))
        self.history_list = tk.Listbox(
            sidebar, bg="#101820", fg="#d9e3e8", selectbackground="#315568",
            relief="flat", highlightthickness=0, font=("Segoe UI", 9),
            activestyle="none"
        )
        self.history_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.history_list.bind("<<ListboxSelect>>", self.load_selected_history)

        chat = tk.Frame(body, bg="#101820")
        chat.pack(side="left", fill="both", expand=True)
        self.transcript = scrolledtext.ScrolledText(
            chat, wrap="word", state="disabled", bg="#17232c", fg="#e8eef2",
            insertbackground="#ffffff", relief="flat", borderwidth=0,
            font=("Segoe UI", 11), padx=16, pady=14
        )
        self.transcript.pack(fill="both", expand=True)
        self.transcript.tag_config("speaker", foreground="#8be9fd",
                                   font=("Segoe UI", 10, "bold"))
        self.transcript.tag_config("user", foreground="#ffd580",
                                   font=("Segoe UI", 10, "bold"))
        self.transcript.tag_config("body", foreground="#e8eef2",
                                   font=("Segoe UI", 11))

        quick = tk.Frame(chat, bg="#101820")
        quick.pack(fill="x", pady=(10, 0))
        self.entry = tk.Text(
            quick, height=3, wrap="word", bg="#22313b", fg="#f4f7f9",
            insertbackground="#ffffff", relief="flat", font=("Segoe UI", 11),
            padx=10, pady=9
        )
        self.entry.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.entry.bind("<Control-Return>", self._send_shortcut)
        ttk.Button(quick, text="Send", command=self.send_message).pack(
            side="right", fill="y"
        )
        ttk.Label(chat, text="Enter sends with Ctrl+Enter • Local data stays on this device",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

    def _append_message(self, speaker: str, text: str):
        self.transcript.configure(state="normal")
        tag = "user" if speaker == "You" else "speaker"
        self.transcript.insert("end", f"{speaker}\n", tag)
        self.transcript.insert("end", text + "\n\n", "body")
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _send_shortcut(self, _event):
        self.send_message()
        return "break"

    def send_message(self):
        if self.busy:
            return
        text = self.entry.get("1.0", "end").strip()
        if not text:
            return
        self.entry.delete("1.0", "end")
        self._append_message("You", text)
        self.messages.append({"role": "user", "content": text})
        self.busy = True
        self.status_var.set("Thinking…")
        threading.Thread(target=self._get_reply, daemon=True).start()

    def _get_reply(self):
        reply = call_model(self.messages)
        self.root.after(0, self._finish_reply, reply)

    def _finish_reply(self, reply: str):
        self.messages.append({"role": "assistant", "content": reply})
        self._append_message("Echo", reply)
        self.busy = False
        self.status_var.set(f"{VERSION}  •  {'Model ready' if API_KEY else 'Offline tools'}")
        self._save_current_history()

    def _save_current_history(self):
        if not self.messages:
            return
        record = {
            "updated": datetime.now().isoformat(timespec="minutes"),
            "title": next((m["content"][:36] for m in self.messages
                           if m["role"] == "user"), "New chat"),
            "messages": self.messages,
        }
        self.history.insert(0, record)
        self.history = self.history[:30]
        save_json(HISTORY_FILE, self.history)
        self._render_history()

    def _render_history(self):
        self.history_list.delete(0, "end")
        for item in self.history[:30]:
            title = item.get("title", "Chat")
            updated = item.get("updated", "")
            self.history_list.insert("end", f"{title}  ·  {updated}")

    def load_selected_history(self, _event=None):
        selected = self.history_list.curselection()
        if not selected:
            return
        record = self.history[selected[0]]
        self.messages = list(record.get("messages", []))
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        for msg in self.messages:
            self._append_message("You" if msg["role"] == "user" else "Echo",
                                 msg["content"])

    def new_chat(self):
        self._save_current_history()
        self.messages = []
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        self._append_message("Echo", "New chat started.")

    def clear_chat(self):
        if messagebox.askyesno("Clear chat", "Clear the visible conversation?"):
            self.messages = []
            self.transcript.configure(state="normal")
            self.transcript.delete("1.0", "end")
            self.transcript.configure(state="disabled")
            self._append_message("Echo", "Conversation cleared.")

    def save_note_dialog(self):
        title = simpledialog.askstring("Save note", "Note title:", parent=self.root)
        if not title:
            return
        content = simpledialog.askstring("Save note", "Note content:", parent=self.root)
        if content is None:
            return
        self.notes.insert(0, {"title": title.strip(), "content": content,
                              "saved": datetime.now().isoformat(timespec="minutes")})
        save_json(NOTES_FILE, self.notes)
        messagebox.showinfo("Echo notes", "Note saved locally.")

    def view_notes(self):
        win = tk.Toplevel(self.root)
        win.title("Echo — Notes")
        win.geometry("560x440")
        win.configure(bg="#101820")
        area = scrolledtext.ScrolledText(win, wrap="word", font=("Segoe UI", 10),
                                         bg="#17232c", fg="#e8eef2", padx=12, pady=12)
        area.pack(fill="both", expand=True, padx=12, pady=12)
        if not self.notes:
            area.insert("end", "No notes saved yet. Use Save note to add one.")
        else:
            for note in self.notes:
                area.insert("end", f"{note.get('title', 'Untitled')}\n", "title")
                area.insert("end", f"{note.get('saved', '')}\n{note.get('content', '')}\n\n")
            area.tag_config("title", font=("Segoe UI", 11, "bold"), foreground="#8be9fd")
        area.configure(state="disabled")

    def calculator_dialog(self):
        expression = simpledialog.askstring(
            "Echo calculator", "Arithmetic expression (e.g. (12 * 4) / 3):",
            parent=self.root
        )
        if expression is None:
            return
        try:
            result = safe_calculate(expression)
            messagebox.showinfo("Calculator result", f"{expression} = {result}")
        except Exception as exc:
            messagebox.showerror("Calculator error", str(exc))

    def study_dialog(self):
        topic = simpledialog.askstring("Study helper", "What topic are you studying?",
                                       parent=self.root)
        if not topic:
            return
        self.entry.insert("end", f"/study {topic.strip()}")
        self.entry.focus_set()


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    EchoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
