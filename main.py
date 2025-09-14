from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

API_KEY = "8140163908:AAEkDZ7KO9lgehqM1OWP0mxIneNpIqyCthg"
NOTES_PASUM = -1002768555543
ADMIN_NOTES = -4903767516
INTRODUCTION = """
Hello, my name is Mimi. I'm your dedicated Notes PASUM 25/26 Bot!

I apologize as I'm a little barebones right now, because my stupid creator, Anthonny, decided to code this in the middle of the night! However, I will still try my best to support you the best I can!

To use me, please directly message me, and ensure that your questions exceed at least 10 characters with a \"?\" at the very end of your question. Here's an example:

Help - BAD!
How do I solve this question - BAD!
I'm getting really confused because of x and y, could you tell me how to solve it? - GOOD!

If you have any attachments, DO NOT SEND IT SEPARATELY WITH YOUR MESSAGE!

My creator made me so that Faith wouldn't be so overwhelmed in responding to billions of DMs asking for help. Now, please use me as an intermediary for you to ask question! This time, both Anthonny and Faith can actually answer your questions rather than only one person at once.
"""
question_map = {}
app = Application.builder().token(API_KEY).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INTRODUCTION)


question_map = {}  # {admin_msg_id: (q_text, asker, media)}

async def pipe_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    text = (update.message.text or update.message.caption or "").strip()
    asker = update.effective_user.username or update.effective_user.first_name

    if len(text) < 10 or not text.endswith("?"):
        return

    media = None
    sent = None

    if update.message.photo:
        media = ("photo", update.message.photo[-1].file_id)
        sent = await context.bot.send_photo(
            chat_id=ADMIN_NOTES,
            photo=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    elif update.message.document:
        media = ("document", update.message.document.file_id)
        sent = await context.bot.send_document(
            chat_id=ADMIN_NOTES,
            document=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    elif update.message.video:
        media = ("video", update.message.video.file_id)
        sent = await context.bot.send_video(
            chat_id=ADMIN_NOTES,
            video=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    elif update.message.audio:
        media = ("audio", update.message.audio.file_id)
        sent = await context.bot.send_audio(
            chat_id=ADMIN_NOTES,
            audio=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    elif update.message.voice:
        media = ("voice", update.message.voice.file_id)
        sent = await context.bot.send_voice(
            chat_id=ADMIN_NOTES,
            voice=media[1],
            caption=f"Q from @{asker}:\n{text}"
        )
    else:
        sent = await context.bot.send_message(
            chat_id=ADMIN_NOTES,
            text=f"Q from @{asker}:\n{text}"
        )

    if sent:
        question_map[sent.message_id] = (text, asker, media)


async def pipe_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_NOTES or not update.message.reply_to_message:
        return

    replied_id = update.message.reply_to_message.message_id
    if replied_id not in question_map:
        return

    q_text, asker, q_media = question_map[replied_id]
    answerer = update.effective_user.username or update.effective_user.first_name
    a_text = (update.message.text or update.message.caption or "").strip()

    caption = f"Q from @{asker}:\n{q_text}\n\nAnswer from @{answerer}:\n{a_text}"

    # Send Q media first (with Q text), then answer media or text
    if q_media:
        mtype, fid = q_media
        if mtype == "photo":
            await context.bot.send_photo(NOTES_PASUM, fid, caption=f"Q from @{asker}:\n{q_text}")
        elif mtype == "document":
            await context.bot.send_document(NOTES_PASUM, fid, caption=f"Q from @{asker}:\n{q_text}")
        elif mtype == "video":
            await context.bot.send_video(NOTES_PASUM, fid, caption=f"Q from @{asker}:\n{q_text}")
        elif mtype == "audio":
            await context.bot.send_audio(NOTES_PASUM, fid, caption=f"Q from @{asker}:\n{q_text}")
        elif mtype == "voice":
            await context.bot.send_voice(NOTES_PASUM, fid, caption=f"Q from @{asker}:\n{q_text}")
    else:
        await context.bot.send_message(NOTES_PASUM, text=f"Q from @{asker}:\n{q_text}")

    # Now send answer media or plain text
    if update.message.photo:
        await context.bot.send_photo(NOTES_PASUM, update.message.photo[-1].file_id, caption=f"Answer from @{answerer}:\n{a_text}")
    elif update.message.document:
        await context.bot.send_document(NOTES_PASUM, update.message.document.file_id, caption=f"Answer from @{answerer}:\n{a_text}")
    elif update.message.video:
        await context.bot.send_video(NOTES_PASUM, update.message.video.file_id, caption=f"Answer from @{answerer}:\n{a_text}")
    elif update.message.audio:
        await context.bot.send_audio(NOTES_PASUM, update.message.audio.file_id, caption=f"Answer from @{answerer}:\n{a_text}")
    elif update.message.voice:
        await context.bot.send_voice(NOTES_PASUM, update.message.voice.file_id, caption=f"Answer from @{answerer}:\n{a_text}")
    else:
        await context.bot.send_message(NOTES_PASUM, text=f"Answer from @{answerer}:\n{a_text}")


async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(update)

app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, pipe_question))
app.add_handler(MessageHandler(filters.Chat(ADMIN_NOTES) & filters.REPLY & ~filters.COMMAND, pipe_answer))
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.ALL, debug))

app.run_polling()
