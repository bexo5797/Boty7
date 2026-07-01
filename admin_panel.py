import sqlite3
import os
import re
from telegram import Update
from telegram.ext import ContextTypes
from utils import DB_FILE, OWNER_ID, MAINTENANCE_MODE, get_donation_stats, get_mandatory_channels, add_mandatory_channel, remove_mandatory_channel
import utils
from keyboards import admin_panel_keyboard, channels_management_keyboard

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
        
        # عدد القنوات الإجبارية
        channels_count = conn.execute("SELECT COUNT(*) FROM mandatory_channels").fetchone()[0]
        conn.close()
        
        await query.edit_message_text(
            f"📊 **إحصائيات البوت الشاملة:**\n\n"
            f"👤 عدد المستخدمين: {users_count}\n"
            f"📁 العمليات الناجحة: {files_count}\n"
            f"⭐ إجمالي التبرعات: {donations} نجمة\n"
            f"👥 عدد المتبرعين: {donors}\n"
            f"📢 القنوات الإجبارية: {channels_count}\n"
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
                file.startswith("audio_") or file.startswith("large_")):
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

    elif query.data == "admin_channels":
        # عرض إدارة القنوات الإجبارية
        channels = get_mandatory_channels()
        channels_text = ""
        if channels:
            for i, ch in enumerate(channels, 1):
                channels_text += f"{i}. @{ch['username']} - {ch['name']}\n"
        else:
            channels_text = "لا توجد قنوات إجبارية"
        
        await query.edit_message_text(
            f"📢 **إدارة القنوات الإجبارية**\n\n"
            f"القنوات الحالية:\n{channels_text}\n\n"
            f"🔹 أضف قناة جديدة: أرسل @username\n"
            f"🔹 احذف قناة: استخدم الأزرار أدناه\n\n"
            f"⚠️ المستخدمون يجب أن يكونوا مشتركين في جميع القنوات الإجبارية لاستخدام البوت.",
            reply_markup=channels_management_keyboard(channels)
        )
        context.user_data['admin_step'] = 'channels_management'

    elif query.data.startswith("channel_add_"):
        # بدء إضافة قناة جديدة
        context.user_data['admin_step'] = 'adding_channel'
        await query.edit_message_text(
            "➕ **إضافة قناة إجبارية جديدة**\n\n"
            "أرسل الآن معرف القناة (مثل: @my_channel)\n\n"
            "يمكنك إرسال اسم القناة بعد المعرف مفصولاً بمسافة:\n"
            "مثال: @my_channel قناتي الرائعة"
        )

    elif query.data.startswith("channel_remove_"):
        # حذف قناة
        channel_username = query.data.replace("channel_remove_", "")
        if remove_mandatory_channel(channel_username):
            await query.answer("✅ تم حذف القناة بنجاح")
        else:
            await query.answer("❌ فشل حذف القناة", show_alert=True)
        
        # تحديث القائمة
        channels = get_mandatory_channels()
        channels_text = ""
        if channels:
            for i, ch in enumerate(channels, 1):
                channels_text += f"{i}. @{ch['username']} - {ch['name']}\n"
        else:
            channels_text = "لا توجد قنوات إجبارية"
        
        await query.edit_message_text(
            f"📢 **إدارة القنوات الإجبارية**\n\n"
            f"القنوات الحالية:\n{channels_text}\n\n"
            f"🔹 أضف قناة جديدة: أرسل @username\n"
            f"🔹 احذف قناة: استخدم الأزرار أدناه\n\n"
            f"⚠️ المستخدمون يجب أن يكونوا مشتركين في جميع القنوات الإجبارية لاستخدام البوت.",
            reply_markup=channels_management_keyboard(channels)
        )

    elif query.data == "close_admin":
        await query.message.delete()

async def handle_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال القناة من المستخدم"""
    if context.user_data.get('admin_step') != 'adding_channel':
        return
    
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    
    text = update.message.text.strip()
    
    # استخراج معرف القناة والاسم
    parts = text.split(maxsplit=1)
    channel_username = parts[0]
    
    # تنظيف معرف القناة
    channel_username = channel_username.replace('@', '').strip()
    
    # التحقق من صحة المعرف
    if not channel_username:
        await update.message.reply_text("❌ معرف القناة غير صحيح. أرسل معرفاً صالحاً مثل @my_channel")
        return
    
    channel_name = parts[1] if len(parts) > 1 else channel_username
    
    # محاولة التحقق من وجود القناة
    try:
        chat = await context.bot.get_chat(f"@{channel_username}")
        channel_name = chat.title if chat.title else channel_name
        
        if add_mandatory_channel(channel_username, channel_name, user_id):
            await update.message.reply_text(
                f"✅ تم إضافة القناة بنجاح!\n\n"
                f"📢 القناة: @{channel_username}\n"
                f"📝 الاسم: {channel_name}\n\n"
                f"سيُطلب من جميع المستخدمين الاشتراك في هذه القناة."
            )
        else:
            await update.message.reply_text("❌ فشل إضافة القناة. قد تكون مكررة.")
    
    except Exception as e:
        await update.message.reply_text(
            f"❌ خطأ في التحقق من القناة: {str(e)}\n\n"
            f"تأكد من أن القناة موجودة وأن البوت لديه صلاحية الوصول إليها."
        )
        return
    
    context.user_data['admin_step'] = None
    
    # عرض إدارة القنوات مرة أخرى
    channels = get_mandatory_channels()
    channels_text = ""
    if channels:
        for i, ch in enumerate(channels, 1):
            channels_text += f"{i}. @{ch['username']} - {ch['name']}\n"
    else:
        channels_text = "لا توجد قنوات إجبارية"
    
    await update.message.reply_text(
        f"📢 **إدارة القنوات الإجبارية**\n\n"
        f"القنوات الحالية:\n{channels_text}\n\n"
        f"🔹 أضف قناة جديدة: أرسل @username\n"
        f"🔹 احذف قناة: استخدم الأزرار أدناه\n\n"
        f"⚠️ المستخدمون يجب أن يكونوا مشتركين في جميع القنوات الإجبارية لاستخدام البوت.",
        reply_markup=channels_management_keyboard(channels)
    )
