import os
import subprocess
import asyncio
import sqlite3
import logging
from datetime import datetime
from telegram import Update, LabeledPrice, Invoice
from telegram.ext import ContextTypes
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import cv2
import numpy as np
from io import BytesIO

from utils import (
    check_subscription, is_maintenance, DB_FILE, OWNER_ID, 
    MAX_FILE_SIZE, get_channel_cover, add_user, add_file_record,
    add_donation, get_donation_stats, get_unsubscribed_channels_text,
    get_mandatory_channels, MANDATORY_CHANNELS, add_image_record,
    get_user_stats
)
from keyboards import main_menu_keyboard, quality_keyboard, my_song_menu_keyboard, admin_panel_keyboard

# ============================================
# دوال تحسين الصور بالذكاء الاصطناعي
# ============================================

def apply_ai_enhancement(image_array, enhancement_type='standard'):
    """
    تطبيق تحسينات بالذكاء الاصطناعي على الصورة
    يستخدم تقنيات متعددة لمحاكاة تحسينات Remini
    """
    try:
        # تحويل الصورة إلى RGB إذا كانت BGR
        if len(image_array.shape) == 3 and image_array.shape[2] == 3:
            # افتراض أنها BGR من OpenCV
            image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image_array
        
        # تطبيق سلسلة من التحسينات
        enhanced = image_rgb.copy()
        
        # 1. تحسين الوضوح باستخدام Unsharp Masking مع AI
        enhanced = ai_sharpening(enhanced, enhancement_type)
        
        # 2. تحسين التباين باستخدام CLAHE محسّن
        enhanced = ai_contrast_enhancement(enhanced, enhancement_type)
        
        # 3. تحسين الألوان باستخدام تصحيح الألوان الذكي
        enhanced = ai_color_enhancement(enhanced, enhancement_type)
        
        # 4. تقليل الضوضاء باستخدام Non-Local Means
        enhanced = ai_denoising(enhanced, enhancement_type)
        
        # 5. تحسين التفاصيل (Edge Enhancement)
        enhanced = ai_detail_enhancement(enhanced, enhancement_type)
        
        # 6. تحسين الإضاءة باستخدام Histogram Equalization
        if enhancement_type in ['premium', 'super']:
            enhanced = ai_lighting_enhancement(enhanced)
        
        # 7. تحسين الدقة (Super Resolution) للتحسين الفائق
        if enhancement_type == 'super':
            enhanced = ai_super_resolution(enhanced)
        
        return enhanced
        
    except Exception as e:
        logging.error(f"❌ خطأ في تحسين AI: {e}")
        return image_array

def ai_sharpening(image, level='standard'):
    """تحسين الوضوح باستخدام تقنيات AI"""
    try:
        # استخدام Gaussian + Unsharp Masking محسّن
        sigma = 1.0
        if level == 'standard':
            amount = 1.2
        elif level == 'premium':
            amount = 1.8
        else:
            amount = 2.5
        
        # Gaussian blur
        blurred = cv2.GaussianBlur(image, (0, 0), sigma)
        
        # Unsharp mask
        sharpened = cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0)
        
        # Clip values
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
        
        return sharpened
    except:
        return image

def ai_contrast_enhancement(image, level='standard'):
    """تحسين التباين باستخدام CLAHE المحسّن"""
    try:
        # تحويل إلى LAB
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        
        # تحديد قوة CLAHE
        if level == 'standard':
            clip_limit = 2.0
            tile_size = (8, 8)
        elif level == 'premium':
            clip_limit = 3.0
            tile_size = (8, 8)
        else:
            clip_limit = 4.0
            tile_size = (4, 4)
        
        # تطبيق CLAHE
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
        l_enhanced = clahe.apply(l)
        
        # دمج القنوات
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
        
        return result
    except:
        return image

def ai_color_enhancement(image, level='standard'):
    """تحسين الألوان باستخدام تصحيح الألوان الذكي"""
    try:
        # تحويل إلى HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)
        
        # تحسين التشبع
        if level == 'standard':
            s_factor = 1.15
        elif level == 'premium':
            s_factor = 1.3
        else:
            s_factor = 1.5
        
        s_enhanced = np.clip(s * s_factor, 0, 255).astype(np.uint8)
        
        # تحسين السطوع
        if level in ['premium', 'super']:
            v_factor = 1.05
            v_enhanced = np.clip(v * v_factor, 0, 255).astype(np.uint8)
        else:
            v_enhanced = v
        
        # دمج القنوات
        hsv_enhanced = cv2.merge([h, s_enhanced, v_enhanced])
        result = cv2.cvtColor(hsv_enhanced, cv2.COLOR_HSV2RGB)
        
        # تصحيح توازن الألوان الأبيض (للمستويات المتقدمة)
        if level in ['premium', 'super']:
            result = auto_white_balance(result)
        
        return result
    except:
        return image

def auto_white_balance(image):
    """تصحيح توازن الألوان الأبيض تلقائياً"""
    try:
        # استخدام طريقة Gray World
        result = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        avg_a = np.mean(result[:, :, 1])
        avg_b = np.mean(result[:, :, 2])
        
        result[:, :, 1] = result[:, :, 1] - ((avg_a - 128) * (result[:, :, 0] / 255.0))
        result[:, :, 2] = result[:, :, 2] - ((avg_b - 128) * (result[:, :, 0] / 255.0))
        
        result = cv2.cvtColor(result, cv2.COLOR_LAB2RGB)
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        return result
    except:
        return image

def ai_denoising(image, level='standard'):
    """تقليل الضوضاء باستخدام تقنيات متقدمة"""
    try:
        if level == 'standard':
            h = 3
            template_window = 7
            search_window = 21
        elif level == 'premium':
            h = 5
            template_window = 7
            search_window = 21
        else:
            h = 7
            template_window = 5
            search_window = 15
        
        # استخدام Non-Local Means Denoising
        denoised = cv2.fastNlMeansDenoisingColored(
            image, None, h, h, template_window, search_window
        )
        
        return denoised
    except:
        return image

def ai_detail_enhancement(image, level='standard'):
    """تحسين التفاصيل الدقيقة في الصورة"""
    try:
        # استخراج التفاصيل باستخدام مرشح Gaussian
        if level == 'standard':
            sigma = 2.0
            strength = 0.3
        elif level == 'premium':
            sigma = 1.5
            strength = 0.5
        else:
            sigma = 1.0
            strength = 0.8
        
        # Gaussian blur
        blurred = cv2.GaussianBlur(image, (0, 0), sigma)
        
        # استخراج التفاصيل
        detail = cv2.subtract(image, blurred)
        
        # تعزيز التفاصيل
        enhanced = cv2.addWeighted(image, 1.0, detail, strength, 0)
        enhanced = np.clip(enhanced, 0, 255).astype(np.uint8)
        
        return enhanced
    except:
        return image

def ai_lighting_enhancement(image):
    """تحسين الإضاءة باستخدام تقنيات متقدمة"""
    try:
        # تحويل إلى HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)
        
        # تطبيق Gamma correction على قناة السطوع
        gamma = 1.1
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        v_enhanced = cv2.LUT(v, table)
        
        # دمج القنوات
        hsv_enhanced = cv2.merge([h, s, v_enhanced])
        result = cv2.cvtColor(hsv_enhanced, cv2.COLOR_HSV2RGB)
        
        return result
    except:
        return image

def ai_super_resolution(image, scale=2):
    """تحسين دقة الصورة (Super Resolution)"""
    try:
        height, width = image.shape[:2]
        new_width = width * scale
        new_height = height * scale
        
        # استخدام العديد من طرق التحسين للحصول على أفضل نتيجة
        # 1. Resize باستخدام interpolation متقدم
        upscaled = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        
        # 2. تطبيق تحسينات إضافية على الصورة المكبرة
        # Unsharp Masking
        blurred = cv2.GaussianBlur(upscaled, (0, 0), 1.0)
        upscaled = cv2.addWeighted(upscaled, 1.5, blurred, -0.5, 0)
        
        # 3. تقليل الضوضاء
        upscaled = cv2.fastNlMeansDenoisingColored(upscaled, None, 5, 5, 7, 21)
        
        # 4. تحسين التباين
        lab = cv2.cvtColor(upscaled, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        upscaled = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
        
        upscaled = np.clip(upscaled, 0, 255).astype(np.uint8)
        
        return upscaled
    except:
        return image

def enhance_portrait(image):
    """تحسين خاص للصور الشخصية (Portrait Enhancement)"""
    try:
        # كشف الوجوه وتطبيق تحسينات خاصة
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            # تطبيق تحسينات على الوجوه المكتشفة
            for (x, y, w, h) in faces:
                # توسيع منطقة الوجه قليلاً
                x = max(0, x - int(w * 0.1))
                y = max(0, y - int(h * 0.1))
                w = min(image.shape[1] - x, int(w * 1.2))
                h = min(image.shape[0] - y, int(h * 1.2))
                
                # استخراج منطقة الوجه
                face_region = image[y:y+h, x:x+w]
                
                if face_region.size > 0:
                    # تحسين نعومة البشرة
                    face_region = cv2.bilateralFilter(face_region, 9, 75, 75)
                    
                    # تحسين التباين في منطقة الوجه
                    lab = cv2.cvtColor(face_region, cv2.COLOR_RGB2LAB)
                    l, a, b = cv2.split(lab)
                    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                    l_enhanced = clahe.apply(l)
                    lab_enhanced = cv2.merge([l_enhanced, a, b])
                    face_region = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)
                    
                    # إعادة وضع منطقة الوجه
                    image[y:y+h, x:x+w] = face_region
        
        return image
    except:
        return image

def apply_ai_enhancement_full(image_path, enhancement_type='standard'):
    """
    تطبيق تحسينات AI متكاملة على الصورة
    """
    try:
        # قراءة الصورة
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        # تطبيق التحسينات
        enhanced = apply_ai_enhancement(image, enhancement_type)
        
        # تحسين الصور الشخصية (للمستويات المتقدمة)
        if enhancement_type in ['premium', 'super']:
            enhanced = enhance_portrait(enhanced)
        
        # حفظ الصورة
        output_path = image_path.replace('input_', 'ai_enhanced_')
        cv2.imwrite(output_path, cv2.cvtColor(enhanced, cv2.COLOR_RGB2BGR), 
                   [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        return output_path
        
    except Exception as e:
        logging.error(f"❌ خطأ في تحسين AI: {e}")
        return None

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
        f"🤖 **مرحباً بك {user.first_name} في بوت تحسين الصور بالذكاء الاصطناعي!**\n\n"
        "✨ باستخدام تقنيات الذكاء الاصطناعي المتقدمة، يمكنني تحسين صورك بشكل مذهل.\n\n"
        "🔹 **مميزات البوت:**\n"
        "• 🧠 تحسين بالذكاء الاصطناعي\n"
        "• 📸 تحسين الوضوح والتفاصيل\n"
        "• 🎨 تحسين الألوان والتباين\n"
        "• 🔍 تقليل الضوضاء\n"
        "• 📈 تحسين الدقة (Super Resolution)\n"
        "• 👤 تحسين الصور الشخصية\n\n"
        "اختر مستوى التحسين المناسب:",
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
            "📸 **تحسين عادي بالذكاء الاصطناعي**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "✅ التحسينات:\n"
            "• تحسين الوضوح\n"
            "• تحسين التباين\n"
            "• تحسين الألوان\n"
            "• تقليل الضوضاء الخفيف"
        )
    
    elif data == "enhance_premium":
        context.user_data['enhancement_type'] = 'premium'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "✨ **تحسين متقدم بالذكاء الاصطناعي**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "✅ التحسينات:\n"
            "• تحسين الوضوح المتقدم\n"
            "• تحسين التباين العالي\n"
            "• تحسين الألوان الغنية\n"
            "• تقليل الضوضاء القوي\n"
            "• تحسين التفاصيل\n"
            "• تحسين الصور الشخصية"
        )
    
    elif data == "enhance_super":
        context.user_data['enhancement_type'] = 'super'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "🚀 **تحسين فائق بالذكاء الاصطناعي**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "✅ التحسينات:\n"
            "• تحسين الدقة (Super Resolution x2)\n"
            "• تحسين الوضوح المتقدم جداً\n"
            "• تحسين الألوان والإضاءة\n"
            "• تقليل الضوضاء المتقدم\n"
            "• تحسين التفاصيل الدقيقة\n"
            "• تحسين الصور الشخصية\n"
            "• تحسين الإضاءة الذكي"
        )
    
    elif data == "enhance_custom":
        context.user_data['step'] = 'selecting_level'
        await query.edit_message_text(
            "🎯 **اختر مستوى التحسين بالذكاء الاصطناعي**\n\n"
            "اختر المستوى المطلوب (1-5):\n"
            "⭐ 1 = تحسين خفيف\n"
            "⭐ 2 = تحسين متوسط\n"
            "⭐ 3 = تحسين جيد\n"
            "⭐ 4 = تحسين متقدم\n"
            "⭐ 5 = تحسين فائق",
            reply_markup=quality_keyboard(None)
        )
    
    elif data.startswith("level_"):
        level = int(data.split("_")[1])
        # تحويل المستوى إلى نوع تحسين
        if level <= 2:
            enhancement_type = 'standard'
        elif level <= 3:
            enhancement_type = 'premium'
        else:
            enhancement_type = 'super'
        
        context.user_data['enhancement_type'] = enhancement_type
        context.user_data['custom_level'] = level
        context.user_data['step'] = 'waiting_for_image'
        
        level_names = {1: "خفيف", 2: "متوسط", 3: "جيد", 4: "متقدم", 5: "فائق"}
        await query.edit_message_text(
            f"🎯 **تم اختيار المستوى {level} ({level_names[level]})**\n\n"
            f"🧠 جاري تجهيز تحسين بالذكاء الاصطناعي...\n\n"
            f"أرسل الصورة التي تريد تحسينها."
        )
    
    elif data == "mysong_edit":
        context.user_data['enhancement_type'] = 'standard'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "📸 **تحسين بالذكاء الاصطناعي**\n\n"
            "أرسل الصورة التي تريد تحسينها."
        )
    
    elif data == "mysong_extract":
        context.user_data['enhancement_type'] = 'premium'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "✨ **تحسين متقدم بالذكاء الاصطناعي**\n\n"
            "أرسل الصورة التي تريد تحسينها."
        )
    
    elif data == "mysong_new":
        context.user_data['enhancement_type'] = 'super'
        context.user_data['step'] = 'waiting_for_image'
        await query.edit_message_text(
            "🚀 **تحسين فائق بالذكاء الاصطناعي**\n\n"
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
            f"🧠 جميع التحسينات باستخدام الذكاء الاصطناعي"
        )

# ============================================
# معالج الصور (التحسين بالذكاء الاصطناعي)
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
    
    wait_msg = await update.message.reply_text(
        "🧠 **جاري تحسين الصورة بالذكاء الاصطناعي...**\n\n"
        "⏳ قد يستغرق هذا بضع ثوانٍ حسب حجم الصورة."
    )
    
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
        
        # تحديث رسالة التقدم
        await wait_msg.edit_text(
            f"🧠 **جاري تحسين الصورة...**\n\n"
            f"📸 نوع التحسين: {enhancement_type}\n"
            f"⭐ المستوى: {level if level else 2}\n"
            f"⏳ جاري تطبيق خوارزميات الذكاء الاصطناعي..."
        )
        
        # تطبيق تحسينات الذكاء الاصطناعي
        enhanced_path = apply_ai_enhancement_full(input_path, enhancement_type)
        
        if not enhanced_path or not os.path.exists(enhanced_path):
            await wait_msg.edit_text("❌ حدث خطأ أثناء تحسين الصورة بالذكاء الاصطناعي.")
            if os.path.exists(input_path):
                os.remove(input_path)
            return
        
        # الحصول على حجم الملف بعد التحسين
        processed_size = os.path.getsize(enhanced_path)
        
        # معلومات التحسين
        enhancement_names = {
            'standard': '📸 تحسين عادي',
            'premium': '✨ تحسين متقدم',
            'super': '🚀 تحسين فائق'
        }
        
        level_emoji = {1: '⭐', 2: '⭐⭐', 3: '⭐⭐⭐', 4: '⭐⭐⭐⭐', 5: '⭐⭐⭐⭐⭐'}
        level_text = f"{level_emoji.get(level, '⭐')} المستوى {level}" if level else "تلقائي"
        
        # إرسال الصورة المحسنة
        with open(enhanced_path, 'rb') as f:
            await update.message.reply_photo(
                photo=f,
                caption=f"✅ **تم تحسين الصورة بالذكاء الاصطناعي!**\n\n"
                       f"🧠 {enhancement_names.get(enhancement_type, 'تحسين')}\n"
                       f"📊 {level_text}\n"
                       f"📦 الحجم الأصلي: {original_size // 1024} KB\n"
                       f"📦 الحجم بعد التحسين: {processed_size // 1024} KB\n"
                       f"📈 نسبة التحسين: {((processed_size - original_size) / original_size * 100):.1f}%\n\n"
                       f"✨ استمتع بالصورة المحسنة بالذكاء الاصطناعي!"
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
        description="تبرع لدعم استمرارية بوت تحسين الصور بالذكاء الاصطناعي\n"
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
        "🧠 بوت تحسين الصور بالذكاء الاصطناعي\n"
        "- تبرع لإستمرار عمل البوت 🎁\n\n"
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
        f"تبرعك يساعد في استمرارية تطوير البوت وتحسين تقنيات الذكاء الاصطناعي. 🚀"
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
                 f"🆔 معاملة تليجرام: `{payment.telegram_payment_charge_id}`",
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
            "📸 **تحسين الصورة بالذكاء الاصطناعي**\n\n"
            "اختر مستوى التحسين المناسب:",
            reply_markup=my_song_menu_keyboard()
        )
        return
    
    elif user_text == "✨ تحسين متقدم":
        context.user_data['enhancement_type'] = 'premium'
        context.user_data['step'] = 'waiting_for_image'
        await update.message.reply_text(
            "✨ **تحسين متقدم بالذكاء الاصطناعي**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "🧠 سيتم تطبيق خوارزميات الذكاء الاصطناعي المتقدمة."
        )
        return
    
    elif user_text == "🚀 تحسين فائق":
        context.user_data['enhancement_type'] = 'super'
        context.user_data['step'] = 'waiting_for_image'
        await update.message.reply_text(
            "🚀 **تحسين فائق بالذكاء الاصطناعي**\n\n"
            "أرسل الصورة التي تريد تحسينها.\n\n"
            "🧠 سيتم تطبيق أحدث تقنيات الذكاء الاصطناعي لتحسين الصورة."
        )
        return
    
    elif user_text == "📊 إحصائياتي":
        stats = get_user_stats(user_id)
        await update.message.reply_text(
            f"📊 **إحصائياتك الشخصية**\n\n"
            f"📸 عدد الصور المحسنة: **{stats['processed']}**\n"
            f"💾 إجمالي حجم الصور: **{stats['total_size_mb']} MB**\n\n"
            f"🧠 جميع التحسينات باستخدام الذكاء الاصطناعي"
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
    
    elif user_text in ["🎵 تعديل الأغنية", "🎬 استخراج صوت من فيديو", "🖼️ إنشاء أغنية كاملة (اسم + صورة + صوت)"]:
        await update.message.reply_text(
            "🧠 **هذا بوت تحسين الصور بالذكاء الاصطناعي!**\n\n"
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
