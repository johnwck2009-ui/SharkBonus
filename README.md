# SharkBonus 🦈

A lightweight Telegram trivia bot with mixed-category quizzes and virtual Shark Points.

## Features

- 10-question random quiz rounds
- Mixed trivia: football, movies, music, general knowledge, animals, technology, food, geography and more
- Four answer options per question with instant feedback
- 10 Shark Points (SP) per correct answer
- 20 SP bonus for completing a round
- Personal points and quiz statistics
- Top-10 leaderboard
- SQLite storage for player scores

Points are virtual and have no cash or withdrawal value.

## Run locally

1. Install Python 3.10 or newer.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and copy its token.
4. Set the environment variable `BOT_TOKEN`:

   **macOS/Linux**
   ```bash
   export BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
   python main.py
   ```

   **Windows PowerShell**
   ```powershell
   $env:BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
   python main.py
   ```

The database is created automatically at `sharkbonus.db`. Set `DATABASE_PATH` to change its location.

## Deploy on Render

This repository includes a `render.yaml` blueprint for a background worker with a persistent disk.

1. Push this repository to GitHub.
2. In Render, create a new Blueprint and select this repository.
3. Add your Telegram bot token as the secret environment variable `BOT_TOKEN`.
4. Deploy the worker.

Do not commit your bot token or database file to GitHub.

## Commands

- `/start` — open the main menu
- `/quiz` — start a quiz
- `/points` — check your points
- `/leaderboard` — view the top players

## Add questions

Add question objects to the `QUESTIONS` list in `main.py`. The `answer` value is the zero-based index of the correct option (A=0, B=1, C=2, D=3).
