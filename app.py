import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Define your bot token (replace 'YOUR_BOT_TOKEN' with your actual bot token)
BOT_TOKEN = "7681281061:AAGfFSElznb1lcBVS5Wvp9afje2UymlY2zU"

# Define states for the conversation flow
WAITING_FOR_SEARCH = 1
WAITING_FOR_SELECTION = 2

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def search_book(book_name, author_name=None):
    """Search for a book on the Internet Archive and return matching results."""
    query = f"title:{book_name}"
    if author_name:
        query += f" AND creator:{author_name}"

    search_url = "https://archive.org/advancedsearch.php"
    params = {
        "q": query,
        "fl[]": ["identifier", "title", "creator"],
        "rows": 100,
        "page": 1,
        "output": "json"
    }
    response = requests.get(search_url, params=params)
    data = response.json()

    matches = []
    if "response" in data and "docs" in data["response"]:
        docs = data["response"]["docs"]
        if docs:
            for i, doc in enumerate(docs, 1):
                title = doc.get("title", "Unknown Title")
                author = doc.get("creator", ["Unknown Author"])[0]
                identifier = doc.get("identifier", "No Identifier")
                matches.append({"title": title, "author": author, "identifier": identifier})
    return matches

def get_download_link(identifier):
    """Fetch metadata for the given identifier and extract the correct PDF download link."""
    metadata_url = f"https://archive.org/metadata/{identifier}"
    response = requests.get(metadata_url)
    metadata = response.json()

    if "server" in metadata and "dir" in metadata and "files" in metadata:
        server = metadata["server"]
        dir_path = metadata["dir"]

        for file in metadata["files"]:
            if file["name"].endswith(".pdf") and ("PDF" in file["format"] or "text" in file["format"].lower()):
                pdf_name = file["name"]
                download_link = f"https://{server}{dir_path}/{pdf_name.replace(' ', '%20')}"
                return download_link

    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "📚 *Welcome to the Book Finder Bot!* 📚\n\n"
        "Send me the name of a book (and optionally the author) to search for it.",
        parse_mode="Markdown"
    )
    # Set the initial state
    context.user_data["state"] = WAITING_FOR_SEARCH

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input based on the current state."""
    user_input = update.message.text.strip()
    state = context.user_data.get("state", WAITING_FOR_SEARCH)

    if state == WAITING_FOR_SEARCH:
        await update.message.reply_text("🔍 *Searching for your book...*", parse_mode="Markdown")

        # Parse user input
        parts = user_input.split(",")
        book_name = parts[0].strip()
        author_name = parts[1].strip() if len(parts) > 1 else None

        # Search for books
        matches = search_book(book_name, author_name)

        if not matches:
            await update.message.reply_text("❌ *No matches found. Please try again.*", parse_mode="Markdown")
            return

        # Prepare inline buttons for each match
        keyboard = []
        for i, match in enumerate(matches, 1):
            keyboard.append([InlineKeyboardButton(f"{i}. {match['title']} by {match['author']}", callback_data=str(i))])

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send the list of books with inline buttons
        await update.message.reply_text(
            "📚 *Found the following matches:*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        # Store matches and update state
        context.user_data["matches"] = matches
        context.user_data["state"] = WAITING_FOR_SELECTION

async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the user's selection via inline buttons."""
    query = update.callback_query
    await query.answer()

    try:
        selection = int(query.data)
        matches = context.user_data.get("matches", [])

        if 1 <= selection <= len(matches):
            selected_book = matches[selection - 1]
            identifier = selected_book["identifier"]

            # Acknowledge the selection
            await query.edit_message_text(
                f"⏳ *Fetching download link for:* `{selected_book['title']}` by `{selected_book['author']}`...",
                parse_mode="Markdown"
            )

            # Get the download link
            download_link = get_download_link(identifier)

            if download_link:
                await query.edit_message_text(
                    f"✅ *Download link for the PDF:* [Click here]({download_link})",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    "❌ *Could not retrieve a valid download link.*",
                    parse_mode="Markdown"
                )
        else:
            await query.edit_message_text("❌ *Invalid selection. Please try again.*", parse_mode="Markdown")

    except ValueError:
        await query.edit_message_text("❌ *Invalid input. Please try again.*", parse_mode="Markdown")

    # Reset the state to WAITING_FOR_SEARCH
    context.user_data["state"] = WAITING_FOR_SEARCH

async def main():
    """Start the bot."""
    logger.info("Starting the bot...")
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_selection))

    # Start polling
    await application.initialize()
    await application.start()
    logger.info("Bot is now running and polling for updates...")
    await application.updater.start_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
