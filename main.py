import logging
import os
import random
import sqlite3
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("DATABASE_PATH", "sharkbonus.db"))
QUESTIONS_PER_ROUND = 10
POINTS_PER_CORRECT = 10
ROUND_COMPLETION_BONUS = 20

# A starter question bank. Add more questions here as the bot grows.
QUESTIONS = [
    {"category": "Football", "question": "Which country won the 2022 FIFA World Cup?",
     "options": ["France", "Argentina", "Brazil", "Germany"], "answer": 1,
     "explanation": "Argentina defeated France in the final."},
    {"category": "Football", "question": "How many players does one football team have on the pitch at the start of a match?",
     "options": ["9", "10", "11", "12"], "answer": 2,
     "explanation": "A team starts with 11 players."},
    {"category": "Movies", "question": "What is the name of the kingdom in Disney's Frozen?",
     "options": ["Arendelle", "Narnia", "Genovia", "Corona"], "answer": 0,
     "explanation": "Elsa and Anna are from Arendelle."},
    {"category": "Music", "question": "How many strings does a standard guitar usually have?",
     "options": ["4", "5", "6", "7"], "answer": 2,
     "explanation": "A standard guitar usually has six strings."},
    {"category": "General Knowledge", "question": "What is the capital city of Japan?",
     "options": ["Seoul", "Tokyo", "Beijing", "Bangkok"], "answer": 1,
     "explanation": "Tokyo is the capital of Japan."},
    {"category": "Animals", "question": "What is the largest animal in the world?",
     "options": ["African elephant", "Great white shark", "Blue whale", "Giraffe"], "answer": 2,
     "explanation": "The blue whale is the largest known animal."},
    {"category": "Technology", "question": "What does 'CPU' stand for?",
     "options": ["Central Processing Unit", "Computer Power Utility", "Core Program Upload", "Central Program User"], "answer": 0,
     "explanation": "CPU means Central Processing Unit."},
    {"category": "Food", "question": "Which fruit is traditionally used to make guacamole?",
     "options": ["Mango", "Avocado", "Pineapple", "Banana"], "answer": 1,
     "explanation": "Avocado is the main ingredient in guacamole."},
    {"category": "Geography", "question": "Which is the largest ocean on Earth?",
     "options": ["Atlantic", "Indian", "Arctic", "Pacific"], "answer": 3,
     "explanation": "The Pacific is the largest ocean."},
    {"category": "Science", "question": "Which planet is known as the Red Planet?",
     "options": ["Venus", "Mars", "Jupiter", "Mercury"], "answer": 1,
     "explanation": "Mars appears reddish because of iron oxide on its surface."},
    {"category": "Fun Facts", "question": "How many hearts does an octopus have?",
     "options": ["One", "Two", "Three", "Four"], "answer": 2,
     "explanation": "An octopus has three hearts."},
    {"category": "Sports", "question": "How many rings are on the Olympic flag?",
     "options": ["Four", "Five", "Six", "Seven"], "answer": 1,
     "explanation": "The Olympic symbol has five interlocking rings."},
    {"category": "Nature", "question": "What do bees collect from flowers to make honey?",
     "options": ["Nectar", "Sap", "Dew", "Pollen only"], "answer": 0,
     "explanation": "Bees collect nectar and transform it into honey."},
    {"category": "Entertainment", "question": "Which instrument has black and white keys?",
     "options": ["Drum", "Piano", "Trumpet", "Violin"], "answer": 1,
     "explanation": "A piano has a keyboard of black and white keys."},
]

def db_connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    with db_connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                points INTEGER NOT NULL DEFAULT 0,
                quizzes_played INTEGER NOT NULL DEFAULT 0,
                correct_answers INTEGER NOT NULL DEFAULT 0
            )
        """)

def register_user(user):
    with db_connect() as db:
        db.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (user.id, user.username or "", user.first_name or "Player"))

def add_points(user_id, points, correct=False):
    with db_connect() as db:
        db.execute("""
            UPDATE users
            SET points = points + ?, correct_answers = correct_answers + ?
            WHERE user_id = ?
        """, (points, 1 if correct else 0, user_id))

def finish_quiz(user_id):
    with db_connect() as db:
        db.execute(
            "UPDATE users SET quizzes_played = quizzes_played + 1 WHERE user_id = ?",
            (user_id,),
        )

def get_user(user_id):
    with db_connect() as db:
        return db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Quiz", callback_data="play")],
        [InlineKeyboardButton("🪙 My Points", callback_data="points"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")],
    ])

def quiz_keyboard(question_index, options):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{label}. {option}", callback_data=f"answer:{question_index}:{i}")]
        for i, (label, option) in enumerate(zip(("A", "B", "C", "D"), options))
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    text = (
        "🦈 *WELCOME TO SHARKBONUS!*\n\n"
        "Dive into random trivia, fun questions and exciting challenges!\n\n"
        "🎮 Play quick quizzes\n"
        "🪙 Earn Shark Points\n"
        "🏆 See how you rank\n\n"
        "Think you know it all? Let's find out!\n"
        "👇 Tap below to get started."
    )
    await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")

async def show_points(query, user_id):
    user = get_user(user_id)
    await query.edit_message_text(
        f"🪙 *Your Shark Points*\n\n"
        f"Balance: *{user['points']:,} SP*\n"
        f"Quizzes played: {user['quizzes_played']}\n"
        f"Correct answers: {user['correct_answers']}",
        reply_markup=main_menu(), parse_mode="Markdown",
    )

async def show_leaderboard(query):
    with db_connect() as db:
        rows = db.execute(
            "SELECT first_name, username, points FROM users "
            "ORDER BY points DESC, first_name COLLATE NOCASE ASC LIMIT 10"
        ).fetchall()
    if not rows:
        message = "🏆 No players yet. Be the first to play!"
    else:
        lines = ["🏆 *SHARKBONUS LEADERBOARD*", ""]
        medals = ["🥇", "🥈", "🥉"]
        for index, row in enumerate(rows):
            name = f"@{row['username']}" if row["username"] else row["first_name"]
            medal = medals[index] if index < 3 else f"{index + 1}."
            lines.append(f"{medal} {name} — {row['points']:,} SP")
        message = "\n".join(lines)
    await query.edit_message_text(message, reply_markup=main_menu(), parse_mode="Markdown")

async def begin_quiz(query, context, user_id):
    if len(QUESTIONS) < QUESTIONS_PER_ROUND:
        await query.edit_message_text("The question bank needs more questions. Please try again later.")
        return
    selected = random.sample(QUESTIONS, QUESTIONS_PER_ROUND)
    context.user_data["quiz"] = {"questions": selected, "index": 0, "score": 0}
    await send_question(query, context)

async def send_question(query, context):
    quiz = context.user_data.get("quiz")
    if not quiz:
        await query.edit_message_text("No active quiz. Tap Play Quiz to start.", reply_markup=main_menu())
        return
    index = quiz["index"]
    question = quiz["questions"][index]
    text = (
        f"🦈 *SHARKBONUS QUIZ*\n"
        f"Question *{index + 1}/{QUESTIONS_PER_ROUND}*\n"
        f"Category: _{question['category']}_\n\n"
        f"*{question['question']}*"
    )
    await query.edit_message_text(
        text, reply_markup=quiz_keyboard(index, question["options"]), parse_mode="Markdown"
    )

async def handle_answer(query, context, user_id, index, answer_index):
    quiz = context.user_data.get("quiz")
    if not quiz or index != quiz["index"]:
        await query.answer("That question has already passed.", show_alert=True)
        return
    question = quiz["questions"][index]
    if answer_index == question["answer"]:
        quiz["score"] += POINTS_PER_CORRECT
        add_points(user_id, POINTS_PER_CORRECT, correct=True)
        feedback = f"✅ Correct! +{POINTS_PER_CORRECT} SP\n{question['explanation']}"
    else:
        correct_option = question["options"][question["answer"]]
        feedback = f"❌ Not quite! The answer was *{correct_option}*.\n{question['explanation']}"
    await query.answer("Answer recorded!")
    quiz["index"] += 1
    if quiz["index"] >= QUESTIONS_PER_ROUND:
        bonus = ROUND_COMPLETION_BONUS
        add_points(user_id, bonus)
        finish_quiz(user_id)
        total = quiz["score"] + bonus
        context.user_data.pop("quiz", None)
        user = get_user(user_id)
        await query.edit_message_text(
            f"{feedback}\n\n🎉 *ROUND COMPLETE!*\n"
            f"Correct-answer points: {quiz['score']} SP\n"
            f"Completion bonus: +{bonus} SP\n"
            f"*Round total: {total} SP*\n\n"
            f"Your balance: *{user['points']:,} SP*",
            reply_markup=main_menu(), parse_mode="Markdown",
        )
    else:
        next_q = quiz["questions"][quiz["index"]]
        text = (
            f"{feedback}\n\n"
            f"🦈 *Question {quiz['index'] + 1}/{QUESTIONS_PER_ROUND}*\n"
            f"Category: _{next_q['category']}_\n\n"
            f"*{next_q['question']}*"
        )
        await query.edit_message_text(
            text,
            reply_markup=quiz_keyboard(quiz["index"], next_q["options"]),
            parse_mode="Markdown",
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    register_user(query.from_user)
    data = query.data or ""
    if data == "play":
        await query.answer()
        await begin_quiz(query, context, user_id)
    elif data == "points":
        await query.answer()
        await show_points(query, user_id)
    elif data == "leaderboard":
        await query.answer()
        await show_leaderboard(query)
    elif data == "about":
        await query.answer()
        await query.edit_message_text(
            "🦈 *ABOUT SHARKBONUS*\n\n"
            "SharkBonus is a casual trivia bot packed with questions about football, "
            "movies, music, general knowledge, technology and more.\n\n"
            "Play quick quizzes, collect virtual Shark Points and have fun! "
            "Points are for entertainment only and have no cash value.",
            reply_markup=main_menu(), parse_mode="Markdown",
        )
    elif data.startswith("answer:"):
        try:
            _, index, answer_index = data.split(":")
            await handle_answer(query, context, user_id, int(index), int(answer_index))
        except (ValueError, IndexError):
            await query.answer("Something went wrong. Please start a new quiz.", show_alert=True)

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    # Commands can start a quiz without a callback query.
    selected = random.sample(QUESTIONS, QUESTIONS_PER_ROUND)
    context.user_data["quiz"] = {"questions": selected, "index": 0, "score": 0}
    quiz = context.user_data["quiz"]
    q = quiz["questions"][0]
    await update.message.reply_text(
        f"🦈 *SHARKBONUS QUIZ*\nQuestion *1/{QUESTIONS_PER_ROUND}*\n"
        f"Category: _{q['category']}_\n\n*{q['question']}*",
        reply_markup=quiz_keyboard(0, q["options"]), parse_mode="Markdown",
    )

async def points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    user = get_user(update.effective_user.id)
    await update.message.reply_text(
        f"🪙 Your balance: *{user['points']:,} SP*",
        reply_markup=main_menu(), parse_mode="Markdown",
    )

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    with db_connect() as db:
        rows = db.execute(
            "SELECT first_name, username, points FROM users "
            "ORDER BY points DESC, first_name COLLATE NOCASE ASC LIMIT 10"
        ).fetchall()
    lines = ["🏆 *SHARKBONUS LEADERBOARD*", ""]
    for i, row in enumerate(rows):
        name = f"@{row['username']}" if row["username"] else row["first_name"]
        lines.append(f"{i + 1}. {name} — {row['points']:,} SP")
    await update.message.reply_text("\n".join(lines), reply_markup=main_menu(), parse_mode="Markdown")

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is required.")
    init_db()
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("points", points_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("SharkBonus is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
