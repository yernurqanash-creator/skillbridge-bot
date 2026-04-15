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

# --- БАРЛЫҚ МӘТІНДЕР (i18n) ---
UI = {
    "kk": {
        "menu_direction": "🧭 Бағыт таңдау",
        "menu_internship": "🎯 Стажировка табу",
        "menu_roadmap": "🗺 3 айлық roadmap",
        "menu_resume": "📄 Resume анализ",
        "menu_chat": "💬 Еркін чат",
        "menu_reset": "♻️ Тілді/Режимді ауыстыру",
        "welcome": "🚀 *SkillBridge AI*\n\nМен саған:\n• қай IT бағыт саған жақын екенін\n• қай стажировка лайық екенін\n• 3 айлық roadmap\n• resume анализ\nайтып берем.\n\nТөменнен режим таңда:",
        "reset_msg": "♻️ Reset болды.\nҚайта режим таңда:",
        "prompt_direction": "🧭 Қызығатын технологияңды, ұнайтын сабақтарыңды, не жасағаныңды жаз.",
        "prompt_internship": "🎯 Білетін технологияларыңды жаз. Мысалы: Java, Spring, SQL, Git.",
        "prompt_roadmap": "🗺 Қазір не білетініңді және қай бағытқа барғың келетінін жаз.",
        "prompt_resume": "📄 Resume файлыңды жібер (PDF/DOCX/TXT) немесе мәтінін осында таста.",
        "prompt_chat": "💬 Еркін сұрағыңды жаза бер. Мен SkillBridge ретінде жауап берем.",
        "need_resume_mode": "Алдымен *📄 Resume анализ* режимін таңда.",
        "only_files": "Тек PDF, DOCX, TXT жібер.",
        "no_text": "Файлдан мәтін оқылмады.",
        "error": "Қате шықты:",
        "help": "Командалар:\n/start — басты меню\n/help — көмек\n\nResume анализ үшін PDF / DOCX / TXT файл жібер.",
        "resume_ready": "📄 *Resume анализ дайын*",
        "direction": "Бағыт:",
        "skills": "Skills:",
        "not_found": "табылмады",
        "summary": "Қысқаша:",
        "strengths": "*Күшті жақтары:*",
        "gaps": "*Толықтыру керек (Gap-тар):*",
        "matches": "*Лайық стажировкалар:*",
        "roadmap_title": "🗺 *3 айлық roadmap:*",
        "ai_lang": "Kazakh"
    },
    "ru": {
        "menu_direction": "🧭 Выбор направления",
        "menu_internship": "🎯 Найти стажировку",
        "menu_roadmap": "🗺 Roadmap на 3 месяца",
        "menu_resume": "📄 Анализ резюме",
        "menu_chat": "💬 Свободный чат",
        "menu_reset": "♻️ Сменить язык/режим",
        "welcome": "🚀 *SkillBridge AI*\n\nЯ помогу тебе:\n• выбрать подходящее IT-направление\n• найти подходящую стажировку\n• составить roadmap на 3 месяца\n• проанализировать резюме\n\nВыбери режим ниже:",
        "reset_msg": "♻️ Сброс выполнен.\nВыбери режим:",
        "prompt_direction": "🧭 Напиши, какие технологии тебе интересны, любимые предметы и что ты уже создавал.",
        "prompt_internship": "🎯 Напиши технологии, которые ты знаешь. Например: Java, Spring, SQL, Git.",
        "prompt_roadmap": "🗺 Напиши, что ты уже знаешь и в каком направлении хочешь развиваться.",
        "prompt_resume": "📄 Отправь файл резюме (PDF/DOCX/TXT) или вставь текст сюда.",
        "prompt_chat": "💬 Задавай любой вопрос. Я отвечу как ассистент SkillBridge.",
        "need_resume_mode": "Сначала выбери режим *📄 Анализ резюме*.",
        "only_files": "Отправляй только файлы PDF, DOCX, TXT.",
        "no_text": "Текст из файла не прочитан.",
        "error": "Произошла ошибка:",
        "help": "Команды:\n/start — главное меню\n/help — помощь\n\nДля анализа резюме отправь файл PDF / DOCX / TXT.",
        "resume_ready": "📄 *Анализ резюме готов*",
        "direction": "Направление:",
        "skills": "Навыки:",
        "not_found": "не найдены",
        "summary": "Саммари:",
        "strengths": "*Сильные стороны:*",
        "gaps": "*Что нужно подтянуть:*",
        "matches": "*Подходящие стажировки:*",
        "roadmap_title": "🗺 *Roadmap на 3 месяца:*",
        "ai_lang": "Russian"
    },
    "en": {
        "menu_direction": "🧭 Choose Direction",
        "menu_internship": "🎯 Find Internship",
        "menu_roadmap": "🗺 3-Month Roadmap",
        "menu_resume": "📄 Resume Analysis",
        "menu_chat": "💬 Free Chat",
        "menu_reset": "♻️ Change Lang/Mode",
        "welcome": "🚀 *SkillBridge AI*\n\nI can help you:\n• find the right IT direction\n• find a suitable internship\n• create a 3-month roadmap\n• analyze your resume\n\nChoose a mode below:",
        "reset_msg": "♻️ Reset successful.\nChoose a mode:",
        "prompt_direction": "🧭 Write about the technologies you are interested in, your favorite subjects, and what you have built.",
        "prompt_internship": "🎯 List the technologies you know. Example: Java, Spring, SQL, Git.",
        "prompt_roadmap": "🗺 Write down what you currently know and where you want to go.",
        "prompt_resume": "📄 Send your resume file (PDF/DOCX/TXT) or paste the text here.",
        "prompt_chat": "💬 Ask me anything. I will answer as the SkillBridge assistant.",
        "need_resume_mode": "First, select the *📄 Resume Analysis* mode.",
        "only_files": "Send only PDF, DOCX, TXT files.",
        "no_text": "No text could be read from the file.",
        "error": "An error occurred:",
        "help": "Commands:\n/start — main menu\n/help — help\n\nSend a PDF / DOCX / TXT file for resume analysis.",
        "resume_ready": "📄 *Resume Analysis Ready*",
        "direction": "Direction:",
        "skills": "Skills:",
        "not_found": "not found",
        "summary": "Summary:",
        "strengths": "*Strengths:*",
        "gaps": "*Areas for Improvement:*",
        "matches": "*Suitable Internships:*",
        "roadmap_title": "🗺 *3-Month Roadmap:*",
        "ai_lang": "English"
    }
}

INTERNSHIPS = [
    {"id": 1, "title": "Java Backend Intern", "company": "Kaspi Tech", "direction": "backend", "skills": ["java", "spring", "sql", "rest", "git", "docker"], "level": "junior"},
    {"id": 2, "title": "Python Backend Intern", "company": "Kolesa Group", "direction": "backend", "skills": ["python", "django", "fastapi", "sql", "git", "api"], "level": "junior"},
    {"id": 3, "title": "Frontend Intern", "company": "Yandex Qazaqstan", "direction": "frontend", "skills": ["html", "css", "javascript", "react", "git", "typescript"], "level": "junior"},
    {"id": 4, "title": "QA Intern", "company": "EPAM", "direction": "qa", "skills": ["testing", "postman", "api", "sql", "jira", "selenium"], "level": "junior"},
    {"id": 5, "title": "Data Analyst Intern", "company": "Freedom", "direction": "data", "skills": ["python", "sql", "excel", "power bi", "statistics", "pandas"], "level": "junior"},
    {"id": 6, "title": "ML / AI Intern", "company": "InDrive", "direction": "ai", "skills": ["python", "machine learning", "pandas", "numpy", "sklearn", "sql"], "level": "junior"},
    {"id": 7, "title": "Mobile Intern", "company": "Beeline", "direction": "mobile", "skills": ["kotlin", "android", "java", "git", "api"], "level": "junior"},
    {"id": 8, "title": "DevOps Intern", "company": "Aitu Tech", "direction": "devops", "skills": ["linux", "docker", "git", "ci/cd", "bash", "cloud"], "level": "junior"},
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

def language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kk"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
        ]
    ])

def menu_keyboard(lang: str):
    texts = UI[lang]
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(texts["menu_direction"], callback_data="mode_direction"),
            InlineKeyboardButton(texts["menu_internship"], callback_data="mode_internship"),
        ],
        [
            InlineKeyboardButton(texts["menu_roadmap"], callback_data="mode_roadmap"),
            InlineKeyboardButton(texts["menu_resume"], callback_data="mode_resume"),
        ],
        [
            InlineKeyboardButton(texts["menu_chat"], callback_data="mode_chat"),
            InlineKeyboardButton(texts["menu_reset"], callback_data="reset"),
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

def analyze_resume_with_ai(resume_text: str, ai_lang: str):
    prompt = f"""
You are SkillBridge AI.
Analyze this resume text and return STRICT JSON only.
IMPORTANT: The values for 'summary', 'strengths', and 'gaps' MUST be written in {ai_lang} language.

Schema:
{{
  "summary": "short summary in {ai_lang}",
  "direction": "backend/frontend/qa/data/ai/mobile/devops",
  "skills": ["skill1", "skill2"],
  "strengths": ["point1 in {ai_lang}", "point2 in {ai_lang}"],
  "gaps": ["gap1 in {ai_lang}", "gap2 in {ai_lang}"]
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

def roadmap_with_ai(direction: str, skills: list, user_text: str, ai_lang: str):
    prompt = f"""
You are SkillBridge AI.
Write a practical 3-month roadmap in {ai_lang} language for a student.

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

def free_chat_with_ai(user_text: str, mode: str, ai_lang: str):
    prompt = f"""
You are SkillBridge AI.

Identity:
- You are the assistant of SkillBridge startup
- You help students choose IT direction, internships, roadmap, and CV positioning
- Speak naturally, warmly, casually
- Default language for your response MUST BE: {ai_lang}
- Be direct, practical, confident

Current mode: {mode}

User message:
{user_text}
"""
    return openai_text(prompt)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Сәлем! Тілді таңдаңыз / Привет! Выберите язык / Hello! Choose your language:",
        reply_markup=language_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Тіл таңдау логикасы
    if data in ["lang_kk", "lang_ru", "lang_en"]:
        lang_code = data.split("_")[1]
        context.user_data["lang"] = lang_code
        context.user_data["mode"] = "chat"
        
        texts = UI[lang_code]
        await query.edit_message_text(
            texts["welcome"], 
            reply_markup=menu_keyboard(lang_code), 
            parse_mode="Markdown"
        )
        return

    lang = context.user_data.get("lang", "kk")
    texts = UI[lang]

    if data == "reset":
        context.user_data.clear()
        await query.edit_message_text(
            "Тілді таңдаңыз / Выберите язык / Choose language:",
            reply_markup=language_keyboard()
        )
        return

    mapping = {
        "mode_direction": ("direction", texts["prompt_direction"]),
        "mode_internship": ("internship", texts["prompt_internship"]),
        "mode_roadmap": ("roadmap", texts["prompt_roadmap"]),
        "mode_resume": ("resume", texts["prompt_resume"]),
        "mode_chat": ("chat", texts["prompt_chat"]),
    }

    if data in mapping:
        mode, text = mapping[data]
        context.user_data["mode"] = mode
        await query.edit_message_text(text, reply_markup=menu_keyboard(lang))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    mode = context.user_data.get("mode", "chat")
    lang = context.user_data.get("lang", "kk")
    texts = UI[lang]
    ai_lang = texts["ai_lang"]

    if mode == "direction":
        skills = extract_skills_local(user_text)
        direction = detect_direction_local(user_text)
        reply = free_chat_with_ai(
            f"User asks for direction selection.\nText: {user_text}\nDetected direction: {direction}\nSkills: {skills}",
            mode,
            ai_lang
        )
        await update.message.reply_text(reply, reply_markup=menu_keyboard(lang))
        return

    if mode == "internship":
        skills = extract_skills_local(user_text)
        direction = detect_direction_local(user_text)
        matches = top_matches(skills, direction, top_n=5)

        lines = [f"🎯 {texts['matches']}"]
        lines.append(f"{texts['direction']} *{direction}*")
        lines.append("")
        for score, item in matches:
            lines.append(f"*{item['company']}* — {item['title']}")
            lines.append(f"{bars(score)} {score}%")
            lines.append(f"{texts['skills']} {', '.join(item['skills'])}")
            lines.append("")

        ai_tip = free_chat_with_ai(
            f"Give short practical advice for internship targeting. User text: {user_text}. Direction: {direction}. Skills: {skills}",
            mode,
            ai_lang
        )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        await update.message.reply_text(ai_tip, reply_markup=menu_keyboard(lang))
        return

    if mode == "roadmap":
        skills = extract_skills_local(user_text)
        direction = detect_direction_local(user_text)
        roadmap = roadmap_with_ai(direction, skills, user_text, ai_lang)
        await update.message.reply_text(roadmap, reply_markup=menu_keyboard(lang))
        return

    if mode == "resume":
        analysis = analyze_resume_with_ai(user_text, ai_lang)
        skills = analysis.get("skills", []) or extract_skills_local(user_text)
        direction = analysis.get("direction") or detect_direction_local(user_text)
        matches = top_matches(skills, direction, top_n=3)

        lines = []
        lines.append(texts["resume_ready"])
        lines.append(f"{texts['direction']} *{direction}*")
        lines.append(f"{texts['skills']} {', '.join(skills) if skills else texts['not_found']}")
        lines.append("")
        lines.append(f"{texts['summary']} {analysis.get('summary', '-')}")
        lines.append("")
        lines.append(texts["strengths"])
        for s in analysis.get("strengths", []):
            lines.append(f"• {s}")
        lines.append("")
        lines.append(texts["gaps"])
        for g in analysis.get("gaps", []):
            lines.append(f"• {g}")
        lines.append("")
        lines.append(texts["matches"])
        for score, item in matches:
            lines.append(f"• {item['company']} / {item['title']} — {score}%")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=menu_keyboard(lang))
        return

    reply = free_chat_with_ai(user_text, mode, ai_lang)
    await update.message.reply_text(reply, reply_markup=menu_keyboard(lang))

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

    raise ValueError("Only PDF, DOCX, TXT")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    mode = context.user_data.get("mode", "chat")
    lang = context.user_data.get("lang", "kk")
    texts = UI[lang]
    ai_lang = texts["ai_lang"]

    if mode != "resume":
        await update.message.reply_text(texts["need_resume_mode"], parse_mode="Markdown", reply_markup=menu_keyboard(lang))
        return

    suffix = Path(document.file_name or "").suffix.lower()
    if suffix not in [".pdf", ".docx", ".txt"]:
        await update.message.reply_text(texts["only_files"])
        return

    tg_file = await context.bot.get_file(document.file_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = tmp.name

    await tg_file.download_to_drive(custom_path=temp_path)

    try:
        text = extract_text_from_file(temp_path)
        if not text.strip():
            await update.message.reply_text(texts["no_text"])
            return

        analysis = analyze_resume_with_ai(text, ai_lang)
        skills = analysis.get("skills", []) or extract_skills_local(text)
        direction = analysis.get("direction") or detect_direction_local(text)
        matches = top_matches(skills, direction, top_n=5)
        roadmap = roadmap_with_ai(direction, skills, "Resume based roadmap", ai_lang)

        lines = []
        lines.append(texts["resume_ready"])
        lines.append(f"{texts['direction']} *{direction}*")
        lines.append(f"{texts['skills']} {', '.join(skills) if skills else texts['not_found']}")
        lines.append("")
        lines.append(f"*{texts['summary']}* {analysis.get('summary', '-')}")
        lines.append("")
        lines.append(texts["matches"])
        for score, item in matches:
            lines.append(f"• {item['company']} — {item['title']} — {score}%")

        if analysis.get("strengths"):
            lines.append("")
            lines.append(texts["strengths"])
            for s in analysis["strengths"]:
                lines.append(f"• {s}")

        if analysis.get("gaps"):
            lines.append("")
            lines.append(texts["gaps"])
            for g in analysis["gaps"]:
                lines.append(f"• {g}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        await update.message.reply_text(f"{texts['roadmap_title']}\n\n" + roadmap, parse_mode="Markdown", reply_markup=menu_keyboard(lang))

    except Exception as e:
        await update.message.reply_text(f"{texts['error']} {e}")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "kk")
    await update.message.reply_text(UI[lang]["help"])

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

    print("SkillBridge bot is running with 3-language support...")
    app.run_polling()

if __name__ == "__main__":
    main()