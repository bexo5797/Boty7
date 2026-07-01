import os
import subprocess
import asyncio
import sqlite3
import logging
from datetime import datetime
from telegram import Update, LabeledPrice, Invoice
from telegram.ext import ContextTypes
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np

from utils import (
    check_subscription, is_maintenance, DB_FILE, OWNER_ID, 
    MAX_FILE_SIZE, get_channel_cover, add_user, add_file_record,
    add_donation, get_donation_stats, get_unsubscribed_channels_text,
    get_mandatory_channels, MANDATORY_CHANNELS, add_image_record,
    get_user_stats
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

    add_user(user.id, user.first_name, user.username)

    await update.message.reply_text(
        f"📸 **مرحباً بك {user.first_name} في بوت تحسين الصور!**\n\n"
        "✨ أرسل لي صورة وسأقوم بتحسينها باستخدام تقنيات الذكاء الاصطناعي.\n\n"
        "🔹 **المميزات:**\n"
        "• تحسين الوضوح والتباين\n"
        "• تحسين الألوان والإضاءة\n"
        "• تقليل الضوضاء\n"
        "• تحسين الدقة (Super Resolution)\n\n"
        "اختر نوع التحسين من الأزرار أدناه:",
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
    
    # ===== اختيار مستوى التحسين =====
    if data == "enhance_standard":
        context.user_data['enhancement_type'] = 'standard'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "📸 **تحسين عادي**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "✅ التحسينات:\n"
            "• تحسين الوضوح\n"
            "• تحسين التباين\n"
            "• تحسين الألوان"
        )
    
    elif data == "enhance_premium":
        context.user_data['enhancement_type'] = 'premium'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "✨ **تحسين متقدم**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "✅ التحسينات:\n"
            "• تحسين الوضوح المتقدم\n"
            "• تحسين التباين العالي\n"
            "• تحسين الألوان الغنية\n"
            "• تقليل الضوضاء\n"
            "• تحسين الحدة"
        )
    
    elif data == "enhance_super":
        context.user_data['enhancement_type'] = 'super'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "🚀 **تحسين فائق**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "✅ التحسينات:\n"
            "• جميع تحسينات المستوى المتقدم\n"
            "• تحسين الدقة (Super Resolution)\n"
            "• تحسين الإضاءة المتقدمة\n"
            "• تحسين الجودة الشاملة"
        )
    
    elif data == "enhance_custom":
        context.user_data['step'] = 'selecting_level'
        await query.edit_message_text(
            "🎯 **اختر مستوى التحسين**\n\n"
            "اختر المستوى المطلوب (1-5):\n"
            "⭐ 1 = تحسين خفيف\n"
            "⭐ 5 = تحسين قوي",
            reply_markup=quality_keyboard(None)
        )
    
    elif data.startswith("level_"):
        level = int(data.split("_")[1])
        context.user_data['enhancement_type'] = f'custom_{level}'
        context.user_data['custom_level'] = level
        context.user_data['step'] = 'waiting_for_image'
        
        level_names = {1: "خفيف", 2: "متوسط", 3: "جيد", 4: "متقدم", 5: "قوي"}
        await query.edit_message_text(
            f"🎯 **تم اختيار المستوى {level} ({level_names[level]})**\n\n"
            f"أرسل الصورة التي تريد تحسينها."
        )
    
    elif data == "mysong_edit":
        # تحويل إلى تحسين الصورة
        context.user_data['enhancement_type'] = 'standard'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "📸 **تحسين الصورة**\n\n"
            "أرسل الصورة التي تريد تحسينها."
        )
    
    elif data == "mysong_extract":
        # تحويل إلى تحسين متقدم
        context.user_data['enhancement_type'] = 'premium'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "✨ **تحسين متقدم**\n\n"
            "أرسل الصورة التي تريد تحسينها."
        )
    
    elif data == "mysong_new":
        # تحويل إلى تحسين فائق
        context.user_data['enhancement_type'] = 'super'
        context
