import sqlite3
import os
from telegram import Update
from telegram.ext import ContextTypes
from utils import DB_FILE, OWNER_ID, MAINTENANCE_MODE, get_donation_stats
import utils
from keyboards import admin_panel_keyboard

async def panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فتح لوحة تحكم المالك"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ هذه الخاصية متاحة للمطور فقط.")
        return

    await update.message.reply_text(
        "🛠 **لوحة تحكم المطور**\n\n"
        "يمكنك التحكم في البوت من هنا:",
        reply_markup=admin_panel_keyboard(utils.MAINTENANCE_MODE)
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المعالجة الخاصة بأزرار لوحة التحكم"""
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🚫 غير مصرح لك!", show_alert=True)
        return

    if query.data == "admin_stats":
        conn = sqlite3.connect(DB_FILE)
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        files_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        
        # إحصائيات التبرعات
        donations = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM donations").fetchone()[0]
        donors = conn.execute("SELECT COUNT(DISTINCT user_id) FROM donations").fetchone()[0]
        conn.close()
        
        await query.edit_message_text(
            f"📊 **إحصائيات البوت الشاملة:**\n\n"
            f"👤 عدد المستخدمين: {users_count}\n"
            f"📁 العمليات الناجحة: {files_count}\n"
            f"⭐ إجمالي التبرعات: {donations} نجمة\n"
            f"👥 عدد المتبرعين: {donors}\n"
            f"⚙️ وضع الصيانة: {'🟢 مفعل' if utils.MAINTENANCE_MODE else '🔴 غير مفعل'}",
            reply_markup=admin_panel_keyboard(utils.MAINTENANCE_MODE)
        )

    elif query.data == "toggle_maintenance":
        utils.MAINTENANCE_MODE = not utils.MAINTENANCE_MODE
        status_text = "تم تفعيل" if utils.MAINTENANCE_MODE else "تم إيقاف"
        
        await query.answer(f"✅ {status_text} وضع الصيانة")
        await query.edit_message_text(
            f"🛠 تم {status_text} وضع الصيانة.\n\n"
            f"الحالة الحالية: {'🟢 البوت في وضع الصيانة' if utils.MAINTENANCE_MODE else '🔴 البوت يعمل طبيعياً'}",
            reply_markup=admin_panel_keyboard(utils.MAINTENANCE_MODE)
        )

    elif query.data == "admin_broadcast":
        context.user_data['admin_step'] = 'broadcasting'
        await query.edit_message_text(
            "📢 **إذاعة (Broadcast)**\n\n"
            "أرسل الآن الرسالة (نص فقط) ليتم إرسالها لجميع المستخدمين.\n\n"
            "⚠️ تحذير: لا يمكن التراجع عن هذه العملية."
        )

    elif query.data == "admin_clean":
        deleted = 0
        for file in os.listdir():
            if (file.endswith(".mp3") or file.startswith("input_") or 
                file.startswith("output_") or file.startswith("cover_") or
                file.startswith("video_") or file.startswith("extracted_") or
                file.startswith("audio_")):
                try:
                    os.remove(file)
                    deleted += 1
                except:
                    pass
        await query.answer(f"✅ تم حذف {deleted} ملف مؤقت")
        await query.edit_message_text(
            f"🗑 **تنظيف الملفات المؤقتة**\n\n"
            f"تم حذف {deleted} ملف مؤقت بنجاح.",
            reply_markup=admin_panel_keyboard(utils.MAINTENANCE_MODE)
        )

    elif query.data == "admin_stars_stats":
        stats = get_donation_stats()
        
        recent_text = ""
        for i, (uid, amt, date) in enumerate(stats['recent'], 1):
            recent_text += f"{i}. 👤 `{uid}` - ⭐ {amt} - {date}\n"
        
        if not recent_text:
            recent_text = "لا توجد تبرعات مسجلة"
        
        await query.edit_message_text(
            f"⭐ **إحصائيات التبرعات بالنجوم** ⭐\n\n"
            f"💰 إجمالي التبرعات: **{stats['total_stars']}** نجمة\n"
            f"👥 عدد المتبرعين: **{stats['donors_count']}**\n"
            f"📦 عدد التبرعات: **{stats['donations_count']}**\n\n"
            f"📋 **آخر التبرعات:**\n{recent_text}\n\n"
            f"💡 **لتحويل النجوم إلى حسابك:**\n"
            f"اذهب إلى @PremiumBot وأرسل /my_stars",
            reply_markup=admin_panel_keyboard(utils.MAINTENANCE_MODE)
        )

    elif query.data == "close_admin":
        await query.message.delete()