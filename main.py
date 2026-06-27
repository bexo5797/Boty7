import os
import asyncio
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler

from handlers import (
    start_handler, media_handler, text_handler, callback_query_handler, 
    photo_handler, donate_handler, pre_checkout_handler, successful_payment_handler
)
from admin_panel import panel_handler, admin_callback_handler
from utils import auto_clear_cache

# إعدادات الـ Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

def main():
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على BOT_TOKEN في متغيرات البيئة!")
        return

    app = Application.builder().token(TOKEN).build()

    # المهام الدورية - تنظيف الملفات المؤقتة كل 30 دقيقة
    if app.job_queue:
        app.job_queue.run_repeating(
            lambda _: asyncio.create_task(auto_clear_cache()), 
            interval=1800,
            first=60
        )

    # === معالجات الأوامر ===
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("panel", panel_handler))
    
    # === أزرار الكولباك ===
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(admin_|toggle_|close_admin|admin_)"))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # === معالجات الدفع بالنجوم ===
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    
    # === معالجات الوسائط ===
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.Document.IMAGE, photo_handler))
    app.add_handler(MessageHandler(filters.AUDIO, media_handler))
    app.add_handler(MessageHandler(filters.VIDEO, media_handler))
    app.add_handler(MessageHandler(filters.Document.AUDIO, media_handler))
    
    # === معالج النصوص (يأتي أخيراً) ===
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 البوت يعمل الآن بنجاح مع دعم التبرعات بالنجوم...")
    app.run_polling()

if __name__ == "__main__":
    main()