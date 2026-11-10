# SharkBonus AI Assistant 🤖

SharkBonus is now an AI assistant on Telegram. It provides text answers through DeepSeek and ChatGPT, plus AI image generation through Google's Gemini image API (NanoBanana).

## Features

- DeepSeek chat for explanations, answers and everyday questions
- ChatGPT chat as an alternative AI provider
- NanoBanana image generation from text prompts
- Conversation context during a chat (use `/reset` to clear it)
- Private admin panel for promotional content
- Admin can update the promotional image, text and destination link
- Optional scheduled promotions to registered users every 5 or 10 hours
- SQLite storage for users and admin settings

## Required environment variables

Set these in your hosting provider's environment settings. Never commit API keys or bot tokens to GitHub.

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `OPENAI_API_KEY` | OpenAI API key for ChatGPT |
| `GEMINI_API_KEY` | Google AI API key for NanoBanana image generation |

Optional settings:

| Variable | Default | Purpose |
|---|---|---|
| `ADMIN_ID` | `8048582254` | Telegram numeric ID allowed to use /admin |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek chat model |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI chat model |
| `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image` | Gemini image model |
| `DATABASE_PATH` | `sharkbonus.db` | SQLite database location |

Each AI provider is independently configured. If a key is missing, that feature will explain which environment variable is needed.

## Admin panel

Send `/admin` from the authorized admin account.

- Change promotional text
- Upload a new promotional image
- Change or clear the destination link
- Preview the current promotion
- Turn scheduled reminders on or off
- Choose a 5-hour or 10-hour interval

Reminders are disabled by default. When enabled, the bot sends the current promotion to users who have started the bot. Telegram users must start the bot before it can message them.

## Commands

- `/start` — open the AI assistant
- `/admin` — open the admin panel (authorized admin only)
- `/imagine` — switch to image generation mode
- `/reset` — clear your current conversation context
- `/clearlink` — clear the promotion link (admin only)

## Run locally

1. Install Python 3.10 or newer.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set the environment variables listed above.
4. Run:

   ```bash
   python main.py
   ```

## Deploy on Render

The repository includes a Render background-worker blueprint. Set `BOT_TOKEN`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, and `GEMINI_API_KEY` as secret environment variables in Render, then deploy. The SQLite database uses the persistent disk configured in `render.yaml`.

**Note:** NanoBanana generation uses the Gemini API. Ensure the configured Google AI account and selected image model have image-generation access.
