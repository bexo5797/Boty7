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
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "🚀 **تحسين فائق**\n\n"
            "أرسل الصورة التي تريد تحسينها."
        )
    
    elif data == "cancel_action":
        context.user_data.clear()
        await query.edit_message_text(
            "❌ تم إلغاء العملية.",
            reply_markup=main_menu_keyboard()
        )
    
    # ===== أزرار الإحصائيات =====
    elif data == "my_stats":
        stats = get_user_stats(user_id)
        await query.edit_message_text(
            f"📊 **إحصائياتك الشخصية**\n\n"
            f"📸 عدد الصور المحسنة: **{stats['processed']}**\n"
            f"💾 إجمالي حجم الصور: **{stats['total_size_mb']} MB**\n\n"
            f"✨ استمر في تحسين صورك!"
        )

# ============================================
# معالج الصور (التحسين)
# ============================================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    # التحقق من أن المستخدم في وضع تحسين الصورة
    if context.user_data.get('step') != 'waiting_for_image':
        await update.message.reply_text(
            "❌ لم تبدأ عملية تحسين الصورة بعد.\n"
            "استخدم الأزرار لبدء العملية.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    # الحصول على الصورة
    photo = update.message.photo[-1] if update.message.photo else None
    document = update.message.document if update.message.document else None
    
    if not photo and not document:
        await update.message.reply_text("❌ من فضلك أرسل صورة.")
        return
    
    wait_msg = await update.message.reply_text("⏳ جاري تحسين الصورة...")
    
    try:
        # تحميل الصورة
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        input_path = f"input_{user_id}_{timestamp}.jpg"
        
        if photo:
            tg_file = await photo.get_file()
            await tg_file.download_to_drive(input_path)
        else:
            # مستند
            if not document.mime_type.startswith('image/'):
                await wait_msg.edit_text("❌ الملف المرسل ليس صورة.")
                return
            tg_file = await document.get_file()
            await tg_file.download_to_drive(input_path)
        
        # الحصول على حجم الملف الأصلي
        original_size = os.path.getsize(input_path)
        
        # تحديد نوع التحسين
        enhancement_type = context.user_data.get('enhancement_type', 'standard')
        level = context.user_data.get('custom_level', 2)
        
        # معالجة الصورة
        enhanced_path = await enhance_image(input_path, enhancement_type, level)
        
        if not enhanced_path or not os.path.exists(enhanced_path):
            await wait_msg.edit_text("❌ حدث خطأ أثناء تحسين الصورة.")
            if os.path.exists(input_path):
                os.remove(input_path)
            return
        
        # الحصول على حجم الملف بعد التحسين
        processed_size = os.path.getsize(enhanced_path)
        
        # إرسال الصورة المحسنة
        with open(enhanced_path, 'rb') as f:
            await update.message.reply_photo(
                photo=f,
                caption=f"✅ **تم تحسين الصورة بنجاح!**\n\n"
                       f"📸 نوع التحسين: {enhancement_type}\n"
                       f"⭐ مستوى التحسين: {level if level else 2}\n"
                       f"📦 الحجم الأصلي: {original_size // 1024} KB\n"
                       f"📦 الحجم بعد التحسين: {processed_size // 1024} KB\n\n"
                       f"✨ استمتع بالصورة المحسنة!"
            )
        
        # تسجيل العملية في قاعدة البيانات
        add_image_record(user_id, original_size, processed_size, enhancement_type, level or 2)
        
        # حذف الملفات المؤقتة
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(enhanced_path):
            os.remove(enhanced_path)
        
        await wait_msg.delete()
        
    except Exception as e:
        await wait_msg.edit_text(f"❌ حدث خطأ: {str(e)}")
        logging.error(f"❌ خطأ في معالجة الصورة: {e}")
    finally:
        context.user_data.clear()

async def enhance_image(image_path, enhancement_type, level=2):
    """تحسين الصورة حسب النوع"""
    try:
        # قراءة الصورة
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        # التحويل إلى RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        if enhancement_type == 'standard':
            enhanced = await apply_standard_enhancement(image_rgb)
        elif enhancement_type == 'premium':
            enhanced = await apply_premium_enhancement(image_rgb)
        elif enhancement_type == 'super':
            enhanced = await apply_super_enhancement(image_rgb)
        elif enhancement_type.startswith('custom_'):
            enhanced = await apply_custom_enhancement(image_rgb, level)
        else:
            enhanced = await apply_standard_enhancement(image_rgb)
        
        # حفظ الصورة
        output_path = image_path.replace('input_', 'enhanced_')
        result = Image.fromarray(enhanced)
        result.save(output_path, quality=95, optimize=True)
        
        return output_path
        
    except Exception as e:
        logging.error(f"❌ خطأ في تحسين الصورة: {e}")
        return None

async def apply_standard_enhancement(image):
    """تحسين عادي"""
    # تحسين الوضوح
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(image, -1, kernel)
    
    # تحسين التباين
    lab = cv2.cvtColor(sharpened, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l_enhanced = clahe.apply(l)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
    
    return result

async def apply_premium_enhancement(image):
    """تحسين متقدم"""
    # تحسين الوضوح المتقدم
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(image, -1, kernel)
    
    # تحسين التباين
    lab = cv2.cvtColor(sharpened, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
    l_enhanced = clahe.apply(l)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    contrast_enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
    
    # تقليل الضوضاء
    denoised = cv2.fastNlMeansDenoisingColored(contrast_enhanced, None, 10, 10, 7, 21)
    
    # تحسين الألوان
    hsv = cv2.cvtColor(denoised, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(hsv)
    s_enhanced = np.clip(s * 1.2, 0, 255).astype(np.uint8)
    hsv_enhanced = cv2.merge([h, s_enhanced, v])
    result = cv2.cvtColor(hsv_enhanced, cv2.COLOR_HSV2RGB)
    
    return result

async def apply_super_enhancement(image):
    """تحسين فائق"""
    # تطبيق التحسين المتقدم أولاً
    enhanced = await apply_premium_enhancement(image)
    
    # تحسين الدقة (Super Resolution)
    height, width = enhanced.shape[:2]
    new_width = width * 2
    new_height = height * 2
    upscaled = cv2.resize(enhanced, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
    
    # تحسين إضافي
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    result = cv2.filter2D(upscaled, -1, kernel)
    
    return result

async def apply_custom_enhancement(image, level):
    """تحسين مخصص حسب المستوى"""
    # تطبيق تحسينات حسب المستوى
    factor = level / 3.0  # 1-5 -> 0.33-1.67
    
    # تحسين الوضوح
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]]) * factor
    kernel[1,1] = 9 * factor
    sharpened = cv2.filter2D(image, -1, kernel.astype(np.float32))
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
    
    # تحسين التباين
    lab = cv2.cvtColor(sharpened, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.5 + factor, tileGridSize=(8,8))
    l_enhanced = clahe.apply(l)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
    
    # تحسين الألوان إذا كان المستوى عالياً
    if level >= 3:
        hsv = cv2.cvtColor(result, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)
        s_enhanced = np.clip(s * (1.0 + (level - 2) * 0.05), 0, 255).astype(np.uint8)
        hsv_enhanced = cv2.merge([h, s_enhanced, v])
        result = cv2.cvtColor(hsv_enhanced, cv2.COLOR_HSV2RGB)
    
    return result

# ============================================
# معالج الملفات (للتوافق مع الكود القديم)
# ============================================
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الملفات - تم تحويله لمعالجة الصور"""
    await photo_handler(update, context)

# ============================================
# نظام التبرع بالنجوم
# ============================================
async def donate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال فاتورة تبرع بـ 50 نجمة"""
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
    
    invoice = Invoice(
        title="⭐ تبرع بـ 50 نجمة",
        description="تبرع لدعم استمرارية بوت تحسين الصور\n"
                    "شكراً لدعمك! 🙏",
        payload=f"donate_50_{user_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="50 نجمة", amount=50)],
        start_parameter="donate",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False,
    )
    
    await update.message.reply_text(
        "⭐ **تبرع بـ 50 نجمة لدعم البوت** ⭐\n\n"
        "- تبرع لإستمرار عمل بوت تحسين الصور 🎁\n\n"
        "💰 المبلغ: 50 نجمة\n\n"
        "اضغط على الزر أدناه لإتمام الدفع:"
    )
    
    await context.bot.send_invoice(
        chat_id=user_id,
        invoice=invoice,
    )

async def pre_checkout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج ما قبل الدفع"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الدفع الناجح"""
    payment = update.message.successful_payment
    user = update.effective_user
    user_id = user.id
    
    add_donation(user_id, 50, payment.telegram_payment_charge_id)
    
    await update.message.reply_text(
        f"✅ **تم التبرع بنجاح!**\n\n"
        f"شكراً لك {user.first_name} على دعمك للبوت! 🙏\n"
        f"⭐ تم تبرع 50 نجمة.\n\n"
        f"تبرعك يساعد في استمرارية البوت وتطويره. 🚀"
    )
    
    # إشعار للمطور
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"🎉 **تبرع جديد بالنجوم!**\n\n"
                 f"👤 المستخدم: {user.first_name}\n"
                 f"🆔 المعرف: `{user_id}`\n"
                 f"⭐ المبلغ: **50 نجمة**\n"
                 f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                 f"🆔 معاملة تليجرام: `{payment.telegram_payment_charge_id}`\n\n"
                 f"💡 **لتحويل النجوم إلى حسابك:**\n"
                 f"اذهب إلى @PremiumBot وأرسل /my_stars",
        )
    except Exception as e:
        logging.error(f"فشل إرسال إشعار للمطور: {e}")

# ============================================
# معالج النصوص
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id

    # ===== الإذاعة للأدمن =====
    if context.user_data.get('admin_step') == 'broadcasting':
        if user_id != OWNER_ID:
            context.user_data['admin_step'] = None
            return
        
        conn = sqlite3.connect(DB_FILE)
        users = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        
        success_count = 0
        for u in users:
            try: 
                await context.bot.send_message(chat_id=u[0], text=user_text)
                success_count += 1
            except: 
                pass
        
        context.user_data['admin_step'] = None
        await update.message.reply_text(f"✅ تمت الإذاعة بنجاح لـ {success_count} مستخدم.")
        return

    # ===== إضافة قناة جديدة =====
    if context.user_data.get('admin_step') == 'channels_management':
        if user_text.startswith('@'):
            from admin_panel import handle_channel_input
            await handle_channel_input(update, context)
            return

    # ===== التحقق من الاشتراك =====
    if MANDATORY_CHANNELS:
        subscribed = await check_subscription(user_id, context)
        if not subscribed:
            unsubscribed_text = get_unsubscribed_channels_text()
            await update.message.reply_text(unsubscribed_text)
            return

    # ===== أزرار القائمة الرئيسية =====
    
    if user_text == "📸 تحسين الصورة":
        await update.message.reply_text(
            "📸 **تحسين الصورة**\n\n"
            "اختر نوع التحسين المطلوب:",
            reply_markup=my_song_menu_keyboard()
        )
        return
    
    elif user_text == "✨ تحسين متقدم":
        context.user_data['enhancement_type'] = 'premium'
        context.user_data['step'] = 'waiting_for_image'
        await update.message.reply_text(
            "✨ **تحسين متقدم**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "✅ التحسينات:\n"
            "• تحسين الوضوح المتقدم\n"
            "• تحسين التباين العالي\n"
            "• تحسين الألوان الغنية\n"
            "• تقليل الضوضاء"
        )
        return
    
    elif user_text == "🚀 تحسين فائق":
        context.user_data['enhancement_type'] = 'super'
        context.user_data['step'] = 'waiting_for_image'
        await update.message.reply_text(
            "🚀 **تحسين فائق**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "✅ التحسينات:\n"
            "• تحسين الدقة (Super Resolution)\n"
            "• تحسين الوضوح والتباين\n"
            "• تحسين الألوان والإضاءة\n"
            "• تقليل الضوضاء المتقدم"
        )
        return
    
    elif user_text == "📊 إحصائياتي":
        stats = get_user_stats(user_id)
        await update.message.reply_text(
            f"📊 **إحصائياتك الشخصية**\n\n"
            f"📸 عدد الصور المحسنة: **{stats['processed']}**\n"
            f"💾 إجمالي حجم الصور: **{stats['total_size_mb']} MB**\n\n"
            f"✨ استمر في تحسين صورك!"
        )
        return
    
    elif user_text == "🛠 لوحة التحكم":
        if user_id == OWNER_ID:
            from admin_panel import panel_handler
            await panel_handler(update, context)
        else:
            await update.message.reply_text("❌ هذه الخاصية متاحة للمطور فقط.")
        return

    elif user_text == "⭐ تبرع 50 نجمة لدعم البوت":
        await donate_handler(update, context)
        return
    
    elif user_text == "▶️ تشغيل البوت":
        await start_handler(update, context)
        return
    
    elif user_text == "🎵 تعديل الأغنية" or user_text == "🎬 استخراج صوت من فيديو" or user_text == "🖼️ إنشاء أغنية كاملة (اسم + صورة + صوت)":
        await update.message.reply_text(
            "📸 **هذا بوت تحسين الصور!**\n\n"
            "استخدم الأزرار التالية:\n"
            "• 📸 تحسين الصورة\n"
            "• ✨ تحسين متقدم\n"
            "• 🚀 تحسين فائق",
            reply_markup=main_menu_keyboard()
        )
        return
    
    await update.message.reply_text(
        "❓ عذراً، لم أفهم طلبك.\n"
        "الرجاء استخدام الأزرار المتاحة في القائمة.",
        reply_markup=main_menu_keyboard()
    )
