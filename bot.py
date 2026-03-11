import os
import re
import json
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from docx import Document as DocxDocument

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

client = OpenAI(api_key=OPENAI_API_KEY)

INTERNSHIPS = [
    {
        "id": 1,
        "title": "Java Backend Intern",
        "company": "Kaspi Tech",
        "direction": "backend",
        "skills": ["java", "spring", "sql", "rest", "git", "docker"],
        "level": "junior",
    },
    {
        "id": 2,
        "title": "Python Backend Intern",
        "company": "Kolesa Group",
        "direction": "backend",
        "skills": ["python", "django", "fastapi", "sql", "git", "api"],
        "level": "junior",
    },
    {
        "id": 3,
        "title": "Frontend Intern",
        "company": "Yandex Qazaqstan",
        "direction": "frontend",
        "skills": ["html", "css", "javascript", "react", "git", "typescript"],
        "level": "junior",
    },
    {
        "id": 4,
        "title": "QA Intern",
        "company": "EPAM",
        "direction": "qa",
        "skills": ["testing", "postman", "api", "sql", "jira", "selenium"],
        "level": "junior",
    },
    {
        "id": 5,
        "title": "Data Analyst Intern",
        "company": "Freedom",
        "direction": "data",
        "skills": ["python", "sql", "excel", "power bi", "statistics", "pandas"],
        "level": "junior",
    },
    {
        "id": 6,
        "title": "ML / AI Intern",
        "company": "InDrive",
        "direction": "ai",
        "skills": ["python", "machine learning", "pandas", "numpy", "sklearn", "sql"],
        "level": "junior",
    },
    {
        "id": 7,
        "title": "Mobile Intern",
        "company": "Beeline",
        "direction": "mobile",
        "skills": ["kotlin", "android", "java", "git", "api"],
        "level": "junior",
    },
    {
        "id": 8,
        "title": "DevOps Intern",
        "company": "Aitu Tech",
        "direction": "devops",
        "skills": ["linux", "docker", "git", "ci/cd", "bash", "cloud"],
        "level": "junior",
    },
]

DIRECTION_KEYWORDS = {
    "backend": ["backend", "java", "spring", "python", "django", "fastapi", "api", "server"],
    "frontend": ["frontend", "html", "css", "javascript", "react", "typescript", "ui", "ux"],
    "qa": ["qa", "testing", "test", "postman", "selenium", "bug"],
    "data": ["data", "analytics", "analyst", "sql", "power bi", "excel", "dashboard"],
    "ai": ["ai", "ml", "machine learning", "llm", "neural", "python", "model"],
    "mobile": ["mobile", "android", "ios", "kotlin", "swift", "flutter"],
    "devops": ["devops", "docker", "linux", "cloud", "ci/cd", "kubernetes", "bash"],
}

KNOWN_SKILLS = {
    "java", "spring", "spring boot", "python", "django", "fastapi",
    "html", "css", "javascript", "typescript", "react",
    "sql", "git", "docker", "linux", "bash", "api", "rest",
    "testing", "postman", "selenium", "jira",
    "excel", "power bi", "pandas", "numpy", "sklearn",
    "machine learning", "android", "kotlin", "swift", "flutter",
    "cloud", "ci/cd", "kubernetes"
}

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def extract_skills_local(text: str):
    t = normalize_text(text)
    found = []
    for skill in sorted(KNOWN_SKILLS, key=len, reverse=True):
        if skill in t:
            found.append(skill)
    return list(dict.fromkeys(found))

def detect_direction_local(text: str):
    t = normalize_text(text)
    scores = {}
    for direction, words in DIRECTION_KEYWORDS.items():
        scores[direction] = sum(1 for w in words if w in t)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "backend"

def score_internship(user_skills, direction, internship):
    user_skills_set = set(s.lower() for s in user_skills)
    req_set = set(s.lower() for s in internship["skills"])
    overlap = len(user_skills_set & req_set)
    base = int((overlap / max(len(req_set), 1)) * 100)
    direction_bonus = 20 if internship["direction"] == direction else 0
    starter_bonus = 10 if internship["level"] == "junior" else 0
    score = min(base + direction_bonus + starter_bonus, 99)
    return score

def top_matches(user_skills, direction, top_n=5):
    scored = []
    for internship in INTERNSHIPS:
        score = score_internship(user_skills, direction, internship)
        scored.append((score, internship))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_n]

def menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🧭 Бағыт таңдау", callback_data="mode_direction"),
            InlineKeyboardButton("🎯 Стажировка табу", callback_data="mode_internship"),
        ],
        [
            InlineKeyboardButton("🗺 3 айлық roadmap", callback_data="mode_roadmap"),
            InlineKeyboardButton("📄 Resume анализ", callback_data="mode_resume"),
        ],
        [
            InlineKeyboardButton("💬 Еркін чат", callback_data="mode_chat"),
            InlineKeyboardButton("♻️ Reset", callback_data="reset"),
        ]
    ])

def bars(score: int):
    filled = max(1, round(score / 10))
    return "█" * filled + "░" * (10 - filled)

def safe_json_parse(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None

def openai_text(prompt: str) -> str:
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )
    return response.output_text.strip()

def analyze_resume_with_ai(resume_text: str):
    prompt = f"""
You are SkillBridge AI.
Analyze this resume text and return STRICT JSON only.

Schema:
{{
  "summary": "short summary",
  "direction": "backend/frontend/qa/data/ai/mobile/devops",
  "skills": ["skill1", "skill2"],
  "strengths": ["point1", "point2"],
  "gaps": ["gap1", "gap2"]
}}

Resume:
{resume_text[:12000]}
"""
    raw = openai_text(prompt)
    data = safe_json_parse(raw)
    if not data:
        return {
            "summary": "Resume parsed with fallback mode.",
            "direction": detect_direction_local(resume_text),
            "skills": extract_skills_local(resume_text),
            "strengths": ["Motivated candidate"],
            "gaps": ["Need clearer project stack", "Need stronger internship targeting"]
        }
    return data

def roadmap_with_ai(direction: str, skills: list, user_text: str):
    prompt = f"""
You are SkillBridge AI.
Write a practical 3-month roadmap in Kazakh for a student.

Direction: {direction}
Current skills: {skills}
User context: {user_text}

Rules:
- concise but useful
- month by month
- weekly focus
- include mini projects
- include internship prep
- sound like a smart startup mentor
"""
    return openai_text(prompt)

def free_chat_with_ai(user_text: str, mode: str):
    prompt = f"""
You are SkillBridge AI.

Identity:
- You are the assistant of SkillBridge startup
- You help students choose IT direction, internships, roadmap, and CV positioning
- Speak naturally, warmly, casually
- Default language: Kazakh
- If user writes in Russian/English, adapt
- Be direct, practical, confident

Current mode: {mode}

User message:
{user_text}
"""
    return openai_text(prompt)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "chat"
    text = (
        "🚀 *SkillBridge AI*\n\n"
        "Мен саған:\n"
        "• қай IT бағыт саған жақын екенін\n"
        "• қай стажировка лайық екенін\n"
        "• 3 айлық roadmap\n"
        "• resume анализ\n"
        "айтып берем.\n\n"
        "Төменнен режим таңда:"
    )
    await update.message.reply_text(text, reply_markup=menu_keyboard(), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "reset":
        context.user_data.clear()
        context.user_data["mode"] = "chat"
        await query.edit_message_text(
            "♻️ Reset болды.\nҚайта режим таңда:",
            reply_markup=menu_keyboard()
        )
        return

    mapping = {
        "mode_direction": ("direction", "🧭 Қызығатын технологияңды, ұнайтын сабақтарыңды, не жасағаныңды жаз."),
        "mode_internship": ("internship", "🎯 Білетін технологияларыңды жаз. Мысалы: Java, Spring, SQL, Git."),
        "mode_roadmap": ("roadmap", "🗺 Қазір не білетініңді және қай бағытқа барғың келетінін жаз."),
        "mode_resume": ("resume", "📄 Resume файлыңды жібер немесе мәтінін осында таста."),
        "mode_chat": ("chat", "💬 Еркін сұрағыңды жаза бер. Мен SkillBridge ретінде жауап берем."),
    }

    mode, text = mapping[data]
    context.user_data["mode"] = mode
    await query.edit_message_text(text, reply_markup=menu_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    mode = context.user_data.get("mode", "chat")

    if mode == "direction":
        skills = extract_skills_local(user_text)
        direction = detect_direction_local(user_text)
        reply = free_chat_with_ai(
            f"User asks for direction selection.\nText: {user_text}\nDetected direction: {direction}\nSkills: {skills}",
            mode
        )
        await update.message.reply_text(reply, reply_markup=menu_keyboard())
        return

    if mode == "internship":
        skills = extract_skills_local(user_text)
        direction = detect_direction_local(user_text)
        matches = top_matches(skills, direction, top_n=5)

        lines = [f"🎯 *Саған лайық стажировкалар*"]
        lines.append(f"Бағыт: *{direction}*")
        lines.append("")
        for score, item in matches:
            lines.append(f"*{item['company']}* — {item['title']}")
            lines.append(f"{bars(score)} {score}%")
            lines.append(f"Керек skills: {', '.join(item['skills'])}")
            lines.append("")

        ai_tip = free_chat_with_ai(
            f"Give short practical advice in Kazakh for internship targeting. User text: {user_text}. Direction: {direction}. Skills: {skills}",
            mode
        )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        await update.message.reply_text(ai_tip, reply_markup=menu_keyboard())
        return

    if mode == "roadmap":
        skills = extract_skills_local(user_text)
        direction = detect_direction_local(user_text)
        roadmap = roadmap_with_ai(direction, skills, user_text)
        await update.message.reply_text(roadmap, reply_markup=menu_keyboard())
        return

    if mode == "resume":
        analysis = analyze_resume_with_ai(user_text)
        skills = analysis.get("skills", []) or extract_skills_local(user_text)
        direction = analysis.get("direction") or detect_direction_local(user_text)
        matches = top_matches(skills, direction, top_n=3)

        lines = []
        lines.append("📄 *Resume анализ нәтижесі*")
        lines.append(f"Бағыт: *{direction}*")
        lines.append(f"Skills: {', '.join(skills) if skills else 'табылмады'}")
        lines.append("")
        lines.append(f"Қысқаша: {analysis.get('summary', '-')}")
        lines.append("")
        lines.append("*Күшті жақтары:*")
        for s in analysis.get("strengths", []):
            lines.append(f"• {s}")
        lines.append("")
        lines.append("*Gap-тар:*")
        for g in analysis.get("gaps", []):
            lines.append(f"• {g}")
        lines.append("")
        lines.append("*Лайық стажировкалар:*")
        for score, item in matches:
            lines.append(f"• {item['company']} / {item['title']} — {score}%")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=menu_keyboard())
        return

    reply = free_chat_with_ai(user_text, mode)
    await update.message.reply_text(reply, reply_markup=menu_keyboard())

def extract_text_from_file(path: str) -> str:
    ext = Path(path).suffix.lower()

    if ext == ".txt":
        return Path(path).read_text(encoding="utf-8", errors="ignore")

    if ext == ".pdf":
        reader = PdfReader(path)
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)

    if ext == ".docx":
        doc = DocxDocument(path)
        return "\n".join(p.text for p in doc.paragraphs)

    raise ValueError("Қолдайтын форматтар: PDF, DOCX, TXT")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    mode = context.user_data.get("mode", "chat")

    if mode != "resume":
        await update.message.reply_text("Алдымен *📄 Resume анализ* режимін таңда.", parse_mode="Markdown", reply_markup=menu_keyboard())
        return

    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in [".pdf", ".docx", ".txt"]:
        await update.message.reply_text("Тек PDF, DOCX, TXT жібер.")
        return

    tg_file = await context.bot.get_file(document.file_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = tmp.name

    await tg_file.download_to_drive(custom_path=temp_path)

    try:
        text = extract_text_from_file(temp_path)
        if not text.strip():
            await update.message.reply_text("Файлдан мәтін оқылмады.")
            return

        analysis = analyze_resume_with_ai(text)
        skills = analysis.get("skills", []) or extract_skills_local(text)
        direction = analysis.get("direction") or detect_direction_local(text)
        matches = top_matches(skills, direction, top_n=5)
        roadmap = roadmap_with_ai(direction, skills, "Resume based roadmap")

        lines = []
        lines.append("📄 *Resume анализ дайын*")
        lines.append(f"Бағыт: *{direction}*")
        lines.append(f"Skills: {', '.join(skills) if skills else 'табылмады'}")
        lines.append("")
        lines.append(f"*Summary:* {analysis.get('summary', '-')}")
        lines.append("")
        lines.append("*Top internship matches:*")
        for score, item in matches:
            lines.append(f"• {item['company']} — {item['title']} — {score}%")

        if analysis.get("strengths"):
            lines.append("")
            lines.append("*Күшті жақтары:*")
            for s in analysis["strengths"]:
                lines.append(f"• {s}")

        if analysis.get("gaps"):
            lines.append("")
            lines.append("*Толықтыру керек:*")
            for g in analysis["gaps"]:
                lines.append(f"• {g}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        await update.message.reply_text("🗺 *3 айлық roadmap:*\n\n" + roadmap, parse_mode="Markdown", reply_markup=menu_keyboard())

    except Exception as e:
        await update.message.reply_text(f"Қате шықты: {e}")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Командалар:\n"
        "/start — басты меню\n"
        "/help — көмек\n\n"
        "Resume анализ үшін PDF / DOCX / TXT файл жібер."
    )

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN табылмады")
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY табылмады")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("SkillBridge bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()