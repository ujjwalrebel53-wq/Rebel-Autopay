#!/usr/bin/env python3
import logging
import os
import re
from io import BytesIO

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database import PaymentDatabase
from ocr_parser import parse_payment_screenshot
from payment_utils import is_valid_utr, parse_amount, parse_manual_entry

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

AWAITING_UTR, AWAITING_AMOUNT = range(2)

db = PaymentDatabase(os.getenv("PAYMENT_DB_PATH", "payments.db"))


def format_currency(amount: float) -> str:
    if amount == int(amount):
        return f"₹{int(amount):,}"
    return f"₹{amount:,.2f}"


async def save_payment_message(update: Update, utr: str, amount: float) -> None:
    message = update.message
    if message is None:
        return

    if db.utr_exists(utr):
        existing = db.get_by_utr(utr)
        await message.reply_text(
            "Ye UTR pehle se saved hai.\n\n"
            f"UTR: {existing.utr}\n"
            f"Amount: {format_currency(existing.amount)}\n"
            f"Saved at: {existing.created_at}"
        )
        return

    payment = db.add_payment(utr, amount)
    total = db.get_total()
    await message.reply_text(
        "Payment save ho gaya!\n\n"
        f"UTR: {payment.utr}\n"
        f"Amount: {format_currency(payment.amount)}\n"
        f"Saved at: {payment.created_at}\n\n"
        f"Total so far: {format_currency(total)}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Namaste! Main Payment Screenshot Bot hoon.\n\n"
        "Aap payment ka screenshot bhejo, main UTR ID aur amount nikal kar save kar dunga.\n"
        "Agar screenshot se read na ho to manually bhi save kar sakte ho.\n\n"
        "Commands:\n"
        "/add UTR AMOUNT - Manual save (example: /add 123456789012 500)\n"
        "/manual - Step by step manual entry\n"
        "/total - Total payment amount\n"
        "/list - Recent payments\n"
        "/stats - Payment count aur total\n"
        "/cancel - Manual entry cancel\n"
        "/help - Help message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Kaise use karein:\n"
        "1. Payment success ka screenshot bhejo (GPay, PhonePe, Paytm, etc.)\n"
        "2. Bot UTR ID aur amount detect karke save karega\n"
        "3. Agar detect na ho to manual save karo:\n"
        "   • /add 123456789012 500\n"
        "   • ya /manual command use karo\n"
        "   • ya screenshot fail hone par 'Manual Save' button dabao\n\n"
        "Duplicate UTR dubara save nahi hoga.\n"
        "Total amount /total se dekh sakte ho."
    )


async def total_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    total = db.get_total()
    count = db.get_count()
    await update.message.reply_text(
        f"Total Payments: {count}\n"
        f"Total Amount: {format_currency(total)}"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    total = db.get_total()
    count = db.get_count()
    await update.message.reply_text(
        f"Stats:\n"
        f"• Saved payments: {count}\n"
        f"• Total amount: {format_currency(total)}"
    )


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payments = db.get_recent(10)
    if not payments:
        await update.message.reply_text("Abhi koi payment save nahi hai.")
        return

    lines = ["Recent payments:\n"]
    for payment in payments:
        lines.append(
            f"• {format_currency(payment.amount)} | UTR: {payment.utr} | {payment.created_at}"
        )
    await update.message.reply_text("\n".join(lines))


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    args_text = text[len("/add") :].strip()

    if not args_text:
        await update.message.reply_text(
            "Format:\n"
            "/add UTR AMOUNT\n\n"
            "Example:\n"
            "/add 123456789012 500"
        )
        return

    parsed = parse_manual_entry(args_text)
    if parsed is None:
        match = re.match(r"^(\d{10,20})\s+(.+)$", args_text)
        if match and is_valid_utr(match.group(1)):
            amount = parse_amount(match.group(2))
            if amount is not None:
                parsed = (match.group(1), amount)

    if parsed is None:
        await update.message.reply_text(
            "Galat format.\n\n"
            "Sahi format:\n"
            "/add 123456789012 500"
        )
        return

    utr, amount = parsed
    await save_payment_message(update, utr, amount)


async def manual_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Manual payment save\n\n"
        "Pehle UTR number bhejo (10-20 digits):\n"
        "Cancel karne ke liye /cancel likho"
    )
    return AWAITING_UTR


async def manual_start_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Manual payment save\n\n"
        "Pehle UTR number bhejo (10-20 digits):\n"
        "Cancel karne ke liye /cancel likho"
    )
    return AWAITING_UTR


async def manual_receive_utr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    utr = update.message.text.strip()
    if not is_valid_utr(utr):
        await update.message.reply_text(
            "Valid UTR nahi hai.\n"
            "10 se 20 digits ka UTR bhejo.\n"
            "Example: 123456789012"
        )
        return AWAITING_UTR

    context.user_data["manual_utr"] = utr
    await update.message.reply_text(
        f"UTR saved: {utr}\n\n"
        "Ab amount bhejo.\n"
        "Example: 500 ya 500.50"
    )
    return AWAITING_AMOUNT


async def manual_receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    amount = parse_amount(update.message.text)
    if amount is None:
        await update.message.reply_text(
            "Valid amount nahi hai.\n"
            "Example: 500 ya 500.50"
        )
        return AWAITING_AMOUNT

    utr = context.user_data.pop("manual_utr", None)
    if not utr:
        await update.message.reply_text("Session expire ho gaya. Dubara /manual se start karo.")
        return ConversationHandler.END

    await save_payment_message(update, utr, amount)
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("manual_utr", None)
    await update.message.reply_text("Manual entry cancel ho gayi.")
    return ConversationHandler.END


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None:
        return

    await message.reply_text("Screenshot process ho raha hai...")

    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = BytesIO()
    await file.download_to_memory(image_bytes)
    image_bytes.seek(0)

    try:
        parsed, raw_text = parse_payment_screenshot(image_bytes.getvalue())
    except Exception as exc:
        logger.exception("OCR failed")
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Manual Save", callback_data="manual_entry")]]
        )
        await message.reply_text(
            f"Screenshot read nahi ho paya: {exc}\n\n"
            "Manual save karo:\n"
            "/add UTR AMOUNT\n"
            "Example: /add 123456789012 500",
            reply_markup=keyboard,
        )
        return

    if parsed is None:
        preview = raw_text[:300] + ("..." if len(raw_text) > 300 else "")
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Manual Save", callback_data="manual_entry")]]
        )
        await message.reply_text(
            "UTR ya amount detect nahi hua.\n\n"
            "Manual save karo:\n"
            "1. 'Manual Save' button dabao\n"
            "2. Ya likho: /add UTR AMOUNT\n"
            "   Example: /add 123456789012 500\n"
            "3. Ya /manual command use karo\n\n"
            f"Detected text preview:\n{preview or '(kuch text nahi mila)'}",
            reply_markup=keyboard,
        )
        return

    await save_payment_message(update, parsed.utr, parsed.amount)


async def handle_quick_manual_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    if text.startswith("/"):
        return

    parsed = parse_manual_entry(text)
    if parsed is None:
        return

    utr, amount = parsed
    await save_payment_message(update, utr, amount)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN environment variable set karo.\n"
            "BotFather se token lo: https://t.me/BotFather"
        )

    manual_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("manual", manual_start),
            CallbackQueryHandler(manual_start_from_button, pattern="^manual_entry$"),
        ],
        states={
            AWAITING_UTR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_receive_utr)
            ],
            AWAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_receive_amount)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        allow_reentry=True,
    )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("total", total_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(manual_conversation)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quick_manual_text)
    )

    logger.info("Payment bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
