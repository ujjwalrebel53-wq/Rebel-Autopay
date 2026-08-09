#!/usr/bin/env python3
import logging
import os
from io import BytesIO

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database import PaymentDatabase
from ocr_parser import parse_payment_screenshot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

db = PaymentDatabase(os.getenv("PAYMENT_DB_PATH", "payments.db"))


def format_currency(amount: float) -> str:
    if amount == int(amount):
        return f"₹{int(amount):,}"
    return f"₹{amount:,.2f}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Namaste! Main Payment Screenshot Bot hoon.\n\n"
        "Aap payment ka screenshot bhejo, main UTR ID aur amount nikal kar save kar dunga.\n\n"
        "Commands:\n"
        "/total - Total payment amount\n"
        "/list - Recent payments\n"
        "/stats - Payment count aur total\n"
        "/help - Help message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Kaise use karein:\n"
        "1. Payment success ka screenshot lo (GPay, PhonePe, Paytm, etc.)\n"
        "2. Screenshot yahan bot me bhejo\n"
        "3. Bot UTR ID aur amount detect karke save karega\n\n"
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
        await message.reply_text(f"Screenshot read nahi ho paya: {exc}")
        return

    if parsed is None:
        preview = raw_text[:300] + ("..." if len(raw_text) > 300 else "")
        await message.reply_text(
            "UTR ya amount detect nahi hua.\n\n"
            "Tips:\n"
            "• Payment success wala screenshot bhejo\n"
            "• Screenshot clear aur poora ho\n"
            "• UTR / UPI Ref No screen par dikhna chahiye\n\n"
            f"Detected text preview:\n{preview or '(kuch text nahi mila)'}"
        )
        return

    if db.utr_exists(parsed.utr):
        existing = db.get_by_utr(parsed.utr)
        await message.reply_text(
            "Ye UTR pehle se saved hai.\n\n"
            f"UTR: {existing.utr}\n"
            f"Amount: {format_currency(existing.amount)}\n"
            f"Saved at: {existing.created_at}"
        )
        return

    payment = db.add_payment(parsed.utr, parsed.amount)
    total = db.get_total()

    await message.reply_text(
        "Payment save ho gaya!\n\n"
        f"UTR: {payment.utr}\n"
        f"Amount: {format_currency(payment.amount)}\n"
        f"Saved at: {payment.created_at}\n\n"
        f"Total so far: {format_currency(total)}"
    )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN environment variable set karo.\n"
            "BotFather se token lo: https://t.me/BotFather"
        )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("total", total_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Payment bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
