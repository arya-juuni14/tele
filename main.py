import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Define your bot token (replace 'YOUR_BOT_TOKEN' with your actual bot token)
BOT_TOKEN = "8037898907:AAHu-WxUD_wzEKtyksiJubCVg1hWrrPPrSY"

# Define the target bot token and user ID for sending queries
TARGET_BOT_TOKEN = "8075458495:AAHx3Vo90iGxpfsbPHlqMfCNdImfwOpkYT4"  # Replace with the token of the target bot
TARGET_USER_ID = 1308884388  # Replace with the user ID of the recipient

# Sticker File ID (Replace this with your actual sticker file ID)
STICKER_FILE_ID = "CAACAgIAAxkBAAICA2fio1TThV5ON31ovYFzicuajW-EAAI2DwACHgnxSVJVnOnolm17NgQ"


def clean_input(value):
    """Helper function to clean user input: trim spaces and convert to lowercase."""
    return value.strip().lower() if value else None


def send_user_query_to_bot(user_id, username, first_name, last_name, query):
    """
    Send the user's query, user ID, username, and name to another Telegram bot.
    """
    full_name = f"{first_name} {last_name}".strip() if last_name else first_name
    message = (
        f"New Query Received:\n"
        f"User ID: {user_id}\n"
        f"Username: {username or 'Unknown'}\n"
        f"Name: {full_name}\n"
        f"Query: {query}"
    )

    # Send the message to the target bot for the specified user
    url = f"https://api.telegram.org/bot{TARGET_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_USER_ID,
        "text": message,
    }
    response = requests.post(url, json=payload)

    if response.status_code != 200:
        print(f"Failed to send query to target bot. Status Code: {response.status_code}, Response: {response.text}")


def search_book(book_name, author_name=None, year=None, language=None, subject=None):
    """Search for a book on the Internet Archive and return matching results."""
    query_parts = []
    if book_name:
        query_parts.append(f"title:{clean_input(book_name)}")
    if author_name:
        query_parts.append(f"creator:{clean_input(author_name)}")
    if year:
        query_parts.append(f"date:{clean_input(year)}")
    if language:
        query_parts.append(f"language:{clean_input(language)}")
    if subject:
        query_parts.append(f"subject:{clean_input(subject)}")

    # Add the mediatype filter to only include books (texts)
    query_parts.append("mediatype:texts")

    query = " AND ".join(query_parts)

    search_url = "https://archive.org/advancedsearch.php"
    params = {
        "q": query,
        "fl[]": ["identifier", "title", "creator"],
        "rows": 10,
        "page": 1,
        "output": "json"
    }
    response = requests.get(search_url, params=params)
    data = response.json()

    matches = []
    if "response" in data and "docs" in data["response"]:
        docs = data["response"]["docs"]
        if docs:
            for doc in docs:
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
                return f"https://{server}{dir_path}/{pdf_name.replace(' ', '%20')}"

    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "📚 *Welcome to the Book Finder Bot!* 📚\n\n"
        "Send me the details of the book you're looking for:\n"
        "Format: `Book Name, Author Name, Year, Language, Subject`\n"
        "Example: `The Secret, Rhonda Byrne, 2006, eng, Self-Help`\n\n"
        "*Note:* All fields are optional except the book name.",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input and fetch valid download links."""
    user_input = update.message.text.strip()

    # Parse user input into parts
    parts = [part.strip() for part in user_input.split(",")]
    original_parts = parts[:]  # Keep a copy of the original input for reference

    # Extract user details
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    last_name = update.message.from_user.last_name

    # Send the user's query to the target bot
    send_user_query_to_bot(user_id, username, first_name, last_name, user_input)

    await update.message.reply_text("🔍 *Searching for your book...*", parse_mode="Markdown")

    while parts:
        # Reconstruct the query string from the remaining parts
        book_name = parts[0] if len(parts) > 0 else None
        author_name = parts[1] if len(parts) > 1 else None
        year = parts[2] if len(parts) > 2 else None
        language = parts[3] if len(parts) > 3 else None
        subject = parts[4] if len(parts) > 4 else None

        # Notify the user about the current search attempt
        current_query = ", ".join(parts)
        await update.message.reply_text(f"🔎 Trying with: `{current_query}`", parse_mode="Markdown")

        # Perform the search
        matches = search_book(book_name, author_name, year, language, subject)

        if matches:
            # If matches are found, process and send them to the user
            for match in matches:
                download_link = get_download_link(match["identifier"])
                if download_link:
                    response = requests.head(download_link, allow_redirects=True)
                    if response.status_code == 200:  # Link is valid
                        await update.message.reply_text(
                            f"✅ [{match['title']} by {match['author']}]({download_link}) - *Click to Download*",
                            parse_mode="Markdown"
                        )
                    elif response.status_code == 403:  # Link is forbidden
                        read_online_link = f"https://archive.org/details/{match['identifier']}"
                        await update.message.reply_text(
                            f"⚠️ [{match['title']} by {match['author']}] can't be downloaded, but can be read here: [Read Online]({read_online_link})",
                            parse_mode="Markdown"
                        )
                else:
                    # No download link found, provide "Read Online" link
                    read_online_link = f"https://archive.org/details/{match['identifier']}"
                    await update.message.reply_text(
                        f"⚠️ [{match['title']} by {match['author']}] can't be downloaded, but can be read here: [Read Online]({read_online_link})",
                        parse_mode="Markdown"
                    )

            # Send a sticker after all results are sent
            await update.message.reply_sticker(STICKER_FILE_ID)
            return  # Exit the loop once we find matches

        # Remove the last part of the input and try again
        parts.pop()

    # If no matches are found after trying all combinations
    await update.message.reply_text(
        "❌ *No matches found after trying all combinations. Please check for spelling mistakes or try a different query.*",
        parse_mode="Markdown"
    )

    # Send a sticker even if no matches are found
    await update.message.reply_sticker(STICKER_FILE_ID)


def main():
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    application.run_polling()


if __name__ == "__main__":
    main()
