import os
import logging
import fitz  # PyMuPDF
import pandas as pd
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
import os

# -------------------- CONFIG --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CSV_PATH = 'doctor_directory_100.csv'  # ✅ Make sure this file is in the same folder

genai.configure(api_key=GEMINI_API_KEY)
doctor_df = pd.read_csv(CSV_PATH)

# -------------------- LOGGING --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- COMMAND HANDLER --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to CarePilot Bot!\nSend me a health report (PDF), and I’ll summarize it and suggest a doctor.")

# -------------------- PDF PROCESSING --------------------
def extract_text_from_pdf(file_path):
    try:
        doc = fitz.open(file_path)
        text = "".join([page.get_text() for page in doc])
        return text
    except Exception as e:
        return f"❌ PDF error: {e}"

# 🔁 New: Handle general text questions using Gemini
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text

    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        prompt = f"""
You are a helpful medical assistant chatbot.

Answer this user question clearly and professionally:

Question: {question}
"""
        response = model.generate_content(prompt)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"❌ Gemini Error: {e}")

def summarize_text(text):
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    prompt = f"""
You are an intelligent medical assistant AI. 
Analyze the following health report and provide ONLY the most important information in short bullet points:

---
🩺 **Major Health Issues**
- Bullet 1
- Bullet 2

🧠 **Possible Health Conditions**
- Bullet 1
- Bullet 2

👨‍⚕️ **Recommended Doctor or Specialist**
- Bullet 1
- Bullet 2
---

Report:
{text}
"""
    response = model.generate_content(prompt)
    return response.text

def extract_specialist(summary):
    import re
    match = re.findall(r"(Endocrinologist|Hepatologist|Cardiologist|General practitioner|Dermatologist|Neurologist|Orthopedist|Pulmonologist|Psychiatrist|Oncologist|Ophthalmologist|Gynecologist)", summary, re.IGNORECASE)
    return list(set(match))  # remove duplicates

def match_doctors(specialists):
    results = []
    for specialist in specialists:
        matches = doctor_df[doctor_df["Specialist"].str.contains(specialist, case=False, na=False)]
        for _, row in matches.iterrows():
            results.append(f"\n👨‍⚕️ {row['Doctor Name']} ({row['Specialist']})\n🏥 {row['Hospital Name']}\n🕒 Timings: {row['Timings']}")
    return results if results else ["⚠️ No matching doctors found."]

# -------------------- FILE HANDLER --------------------
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if document.mime_type != 'application/pdf':
        await update.message.reply_text("❌ Please send a valid PDF file.")
        return

    # Step 1: Download file
    file = await context.bot.get_file(document.file_id)
    file_path = f"{document.file_name}"
    await file.download_to_drive(file_path)

    # Step 2: Extract text
    await update.message.reply_text("📄 Extracting text from PDF...")
    pdf_text = extract_text_from_pdf(file_path)

    # Step 3: Summarize
    await update.message.reply_text("💡 Summarizing using Gemini AI...")
    summary = summarize_text(pdf_text)
    await update.message.reply_text(f"🧠 Summary & Recommendations:\n\n{summary}")

    # Step 4: Doctor match
    specialists = extract_specialist(summary)
    await update.message.reply_text(f"🔍 Specialists Detected: {', '.join(specialists)}")

    doctor_matches = match_doctors(specialists)
    for match in doctor_matches:
        await update.message.reply_text(match)

    # Step 5: Cleanup
    os.remove(file_path)

# -------------------- MAIN --------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))  # For PDFs
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))  # For chat

    print("✅ Bot is running with chatbot support.")
    app.run_polling()

if __name__ == "__main__":
    main()

