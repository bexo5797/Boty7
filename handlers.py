import os
import subprocess
import asyncio
import sqlite3
import logging
from datetime import datetime
from telegram import Update, LabeledPrice, Invoice
from telegram.ext import ContextTypes
from mutagen.id3 import ID3, TIT2, TPE1, APIC, error as MutagenError

from utils import (
    check_subscription, is_maintenance, DB_FILE, OWNER_ID, 
    MAX_FILE_SIZE, get_channel_cover, add_user, add_file_record,
    add_donation, get_donation_stats, get_unsubscribed_channels_text,
    get_mandatory_channels, MANDATORY_CHANNELS
)
from keyboards import main_menu_keyboard, quality_keyboard, my_song_menu_keyboard, admin_panel_keyboard

# ============================================
# دالة البداية
# ============================================
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): 
        return
    
    user = update.effective_user
    
    # التحقق من الاشتراك في جميع القنوات الإجبارية
    if MANDATORY_CHANNELS:
        subscribed = await check_subscription(user.id, context)
        if not subscribed:
            unsubscribed_text = get_unsubscribed_channels_text()
            await update.message.reply_text(unsubscribed_text)
            return

    add_user(user.id, user.first_name)

    await update.message.reply_text(
        f"🚀 أهلاً بك {user.first_name} في بوت الخدمات الصوتية!\n\n"
        "إختر ما تريد فعله من الأزرار أدناه:",
        reply_markup=main_menu_keyboard()
    )

# ============================================
# معالج الكولباك (الأزرار)
# ============================================
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    await query.answer()
    
    # التحقق من الاشتراك في القنوات الإجبارية
    if MANDATORY_CHANNELS:
        subscribed = await check_subscription(user_id, context)
        if not subscribed:
            unsubscribed_text = get_unsubscribed_channels_text()
            await query.edit_message_text(unsubscribed_text)
            return
    
    # ===== أزرار وضع "أغنيتي" المتكاملة =====
    if data == "mysong_edit":
        context.user_data.clear()
        context.user_data['mode'] = 'mysong_edit'
        context.user_data['step'] = 'waiting_for_audio'
        await query.edit_message_text(
            "🎵 تعديل أغنية موجودة\n\n"
            "📤 أرسل لي الآن الملف الصوتي (MP3) الذي تريد تعديل اسمه وإضافة صورة له.\n\n"
            "⚠️ الحد الأقصى للحجم: 70MB"
        )
    
    elif data == "mysong_extract":
        context.user_data.clear()
        context.user_data['mode'] = 'mysong_extract'
        context.user_data['step'] = 'waiting_for_video'
        await query.edit_message_text(
            "🎬 استخراج صوت من فيديو + إضافة صورة\n\n"
            "📤 أرسل لي الآن ملف الفيديو (MP4) لاستخراج الصوت منه، ثم سنضيف الاسم والصورة.\n\n"
            "⚠️ الحد الأقصى للحجم: 70MB"
        )
    
    elif data == "mysong_new":
        context.user_data.clear()
        context.user_data['mode'] = 'mysong_new'
        context.user_data['step'] = 'waiting_for_audio'
        await query.edit_message_text(
            "🆕 رفع ملف صوتي جديد + صورة\n\n"
            "📤 أرسل لي الآن الملف الصوتي (MP3) وسأطلب منك الاسم والفنان والصورة.\n\n"
            "⚠️ الحد الأقصى للحجم: 70MB"
        )
    
    # ===== أزرار اختيار الجودة =====
    elif data.startswith("q_"):
        parts = data.split("_")
        quality = parts[1] + "k"
        action = parts[2]
        context.user_data['selected_quality'] = quality
        context.user_data['action_type'] = action
        
        if action == "edit":
            msg = "🎵 أرسل الآن الملف الصوتي (MP3) لتعديله:"
        else:
            msg = "🎬 أرسل الآن ملف الفيديو (MP4) لاستخراج الصوت منه:"
        
        await query.edit_message_text(f"✅ تم اختيار جودة {quality}.\n\n{msg}")
    
    elif data == "cancel_action":
        context.user_data.clear()
        await query.edit_message_text("❌ تم إلغاء العملية.")
    
    # ===== أزرار الإحصائيات =====
    elif data == "my_stats":
        conn = sqlite3.connect(DB_FILE)
        files_count = conn.execute(
            "SELECT COUNT(*) FROM files WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        conn.close()
        
        await query.edit_message_text(
            f"📊 إحصائياتك الشخصية\n\n"
            f"✅ عدد الأغاني التي قمت بمعالجتها: {files_count}"
        )

# ============================================
# معالج الملفات (الصوت والفيديو) - مع دعم الملفات الكبيرة
# ============================================
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_maintenance(update, context): 
        return
    
    user_id = update.effective_user.id
    
    # التحقق من الاشتراك في القنوات الإجبارية
    if MANDATORY_CHANNELS:
        subscribed = await check_subscription(user_id, context)
        if not subscribed:
            unsubscribed_text = get_unsubscribed_channels_text()
            await update.message.reply_text(unsubscribed_text)
            return
    
    mode = context.user_data.get('mode')
    step = context.user_data.get('step')
    
    # ===== وضع mysong =====
    if mode and step:
        if step == 'waiting_for_audio' and mode in ['mysong_edit', 'mysong_new']:
            file_obj = None
            if update.message.audio:
                file_obj = update.message.audio
            elif update
