import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram.ext import ContextTypes

# الإعدادات الأساسية
DB_FILE = "bot_stats.db"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB للصور
DEFAULT_QUALITY = 95
CHANNEL_USERNAME = "BEXO50"

# ايدي المالك
OWNER_ID = 8798182716  # ⚠️ غير هذا الرقم إلى معرفك

# وضع الصيانة
MAINTENANCE_MODE = False

# قائمة القنوات الإجبارية
MANDATORY_CHANNELS = []

def init_db():
    """تهيئة قاعدة البيانات عند التشغيل"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # جدول المستخدمين
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, 
                      first_name TEXT, 
                      username TEXT,
                      join_date TEXT,
                      processed_count INTEGER DEFAULT 0)''')
        
        # جدول الصور المعالجة
        c.execute('''CREATE TABLE IF NOT EXISTS processed_images 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      user_id INTEGER, 
                      original_size INTEGER,
                      processed_size INTEGER,
                      enhancement_level INTEGER,
                      enhancement_type TEXT,
                      date TEXT)''')
        
        # جدول التبرعات
        c.execute('''CREATE TABLE IF NOT EXISTS donations 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      user_id INTEGER, 
                      amount INTEGER, 
                      date TEXT,
                      telegram_payment_id TEXT)''')
        
        # جدول القنوات الإجبارية
        c.execute('''CREATE TABLE IF NOT EXISTS mandatory_channels 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      channel_username TEXT UNIQUE,
                      channel_name TEXT,
                      added_by INTEGER,
                      added_date TEXT)''')
        
        # فهارس
        c.execute('''CREATE INDEX IF NOT EXISTS idx_processed_user_id ON processed_images(user_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_processed_date ON processed_images(date)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_donations_user_id ON donations(user_id)''')
        
        conn.commit()
        logging.info("✅ تم تهيئة قاعدة البيانات بنجاح")
        
        load_mandatory_channels()
        
    except Exception as e:
        logging.error(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    finally:
        if conn:
            conn.close()

def load_mandatory_channels():
    """تحميل القنوات الإجبارية من قاعدة البيانات"""
    global MANDATORY_CHANNELS
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        channels = cursor.execute(
            "SELECT channel_username, channel_name FROM mandatory_channels"
        ).fetchall()
        conn.close()
        
        MANDATORY_CHANNELS = [
            {"channel_username": ch[0], "channel_name": ch[1] or ch[0]} 
            for ch in channels
        ]
        logging.info(f"✅ تم تحميل {len(MANDATORY_CHANNELS)} قناة إجبارية")
    except Exception as e:
        logging.error(f"❌ خطأ في تحميل القنوات الإجبارية: {e}")
        MANDATORY_CHANNELS = []

def add_mandatory_channel(channel_username, channel_name, added_by):
    """إضافة قناة إجبارية جديدة"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            """INSERT OR IGNORE INTO mandatory_channels 
               (channel_username, channel_name, added_by, added_date) 
               VALUES (?, ?, ?, ?)""",
            (channel_username, channel_name, added_by, 
             datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()
        load_mandatory_channels()
        return True
    except Exception as e:
        logging.error(f"❌ خطأ في إضافة القناة الإجبارية: {e}")
        return False

def remove_mandatory_channel(channel_username):
    """حذف قناة إجبارية"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "DELETE FROM mandatory_channels WHERE channel_username = ?",
            (channel_username,)
        )
        conn.commit()
        conn.close()
        load_mandatory_channels()
        return True
    except Exception as e:
        logging.error(f"❌ خطأ في حذف القناة الإجبارية: {e}")
        return False

def get_mandatory_channels():
    """الحصول على قائمة القنوات الإجبارية"""
    return MANDATORY_CHANNELS

async def is_maintenance(update, context):
    """التحقق من وضع الصيانة"""
    if MAINTENANCE_MODE:
        if update.effective_user.id == OWNER_ID:
            return False
        
        if update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ **عذراً، البوت في وضع الصيانة حالياً!**\n\n"
                "نحن نقوم ببعض التحديثات، سنعود للعمل قريباً. 🛠️"
            )
        return True
    return False

async def auto_clear_cache():
    """تنظيف الملفات المؤقتة من السيرفر"""
    deleted = 0
    temp_patterns = [
        "enhanced_", "temp_", "_enhanced.", "_pil_enhanced.", 
        "_sr_enhanced.", "_standard_enhanced.", "_premium_enhanced.", 
        "_super_enhanced.", "input_", "output_", "processed_"
    ]
    
    try:
        current_time = datetime.now().timestamp()
        one_hour_ago = current_time - 3600
        
        for file in os.listdir():
            is_temp = any(pattern in file for pattern in temp_patterns)
            
            if is_temp:
                try:
                    file_path = os.path.join(os.getcwd(), file)
                    if os.path.isfile(file_path):
                        if os.path.getmtime(file_path) < one_hour_ago:
                            os.remove(file_path)
                            deleted += 1
                except Exception as e:
                    logging.warning(f"⚠️ فشل حذف الملف {file}: {e}")
        
        if deleted > 0:
            logging.info(f"🧹 تم تنظيف {deleted} ملفات مؤقتة")
            
    except Exception as e:
        logging.error(f"❌ خطأ في تنظيف الملفات المؤقتة: {e}")

async def check_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    """التحقق من الاشتراك في جميع القنوات الإجبارية"""
    if not MANDATORY_CHANNELS:
        return True
    
    try:
        for channel in MANDATORY_CHANNELS:
            username = channel['channel_username']
            if not username.startswith('@'):
                username = f"@{username}"
            
            try:
                member = await context.bot.get_chat_member(username, user_id)
                if member.status in ["left", "kicked"]:
                    return False
            except Exception as e:
                logging.error(f"خطأ في فحص الاشتراك بالقناة {username}: {e}")
                return False
        
        return True
    except Exception as e:
        logging.error(f"خطأ في فحص الاشتراك للمستخدم {user_id}: {e}")
        return True

def get_unsubscribed_channels_text():
    """الحصول على نص القنوات غير المشترك بها"""
    if not MANDATORY_CHANNELS:
        return ""
    
    text = "⚠️ **أنت غير مشترك في القنوات التالية!**\n\n"
    text += "يجب الاشتراك أولاً في القنوات التالية:\n"
    for channel in MANDATORY_CHANNELS:
        username = channel['channel_username']
        if not username.startswith('@'):
            username = f"@{username}"
        text += f"👉 {username} - {channel['channel_name']}\n"
    text += "\nبعد الاشتراك، ارسل /start مرة أخرى."
    return text

async def get_channel_cover(context: ContextTypes.DEFAULT_TYPE):
    """جلب صورة القناة (لم يعد مستخدم للصور)"""
    return None

def add_user(user_id, first_name, username=None):
    """إضافة مستخدم جديد إلى قاعدة البيانات"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            """INSERT OR IGNORE INTO users(user_id, first_name, username, join_date) 
               VALUES (?, ?, ?, ?)""",
            (user_id, first_name, username, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
    except Exception as e:
        logging.error(f"❌ خطأ في إضافة المستخدم {user_id}: {e}")
    finally:
        if conn:
            conn.close()

def add_file_record(user_id, title, artist):
    """تسجيل عملية معالجة صورة (تم تعديلها للصور)"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            """UPDATE users SET processed_count = processed_count + 1 
               WHERE user_id = ?""",
            (user_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"❌ خطأ في تسجيل المعالجة: {e}")
        return False
    finally:
        if conn:
            conn.close()

def add_image_record(user_id, original_size, processed_size, enhancement_type, level):
    """تسجيل صورة معالجة في قاعدة البيانات"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            """INSERT INTO processed_images 
               (user_id, original_size, processed_size, enhancement_level, enhancement_type, date) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, original_size, processed_size, level, enhancement_type, 
             datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        
        # تحديث عدد المعالجات للمستخدم
        conn.execute(
            "UPDATE users SET processed_count = processed_count + 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"❌ خطأ في تسجيل الصورة: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_user_stats(user_id):
    """الحصول على إحصائيات المستخدم"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        processed = cursor.execute(
            "SELECT COUNT(*) FROM processed_images WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        
        total_size = cursor.execute(
            "SELECT COALESCE(SUM(original_size), 0) FROM processed_images WHERE user_id = ?",
            (user_id,)
        ).fetchone()[0]
        
        conn.close()
        
        return {
            "processed": processed,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logging.error(f"❌ خطأ في جلب إحصائيات المستخدم: {e}")
        return {"processed": 0, "total_size_mb": 0}

def add_donation(user_id, amount, payment_id):
    """تسجيل تبرع في قاعدة البيانات"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT INTO donations (user_id, amount, date, telegram_payment_id) VALUES (?, ?, ?, ?)",
            (user_id, amount, datetime.now().strftime("%Y-%m-%d %H:%M"), payment_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"❌ خطأ في تسجيل التبرع: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_donation_stats():
    """الحصول على إحصائيات التبرعات"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        total_stars = cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM donations"
        ).fetchone()[0]
        
        donors_count = cursor.execute(
            "SELECT COUNT(DISTINCT user_id) FROM donations"
        ).fetchone()[0]
        
        donations_count = cursor.execute(
            "SELECT COUNT(*) FROM donations"
        ).fetchone()[0]
        
        recent = cursor.execute(
            "SELECT user_id, amount, date FROM donations ORDER BY id DESC LIMIT 10"
        ).fetchall()
        
        conn.close()
        
        return {
            "total_stars": total_stars,
            "donors_count": donors_count,
            "donations_count": donations_count,
            "recent": recent
        }
    except Exception as e:
        logging.error(f"❌ خطأ في جلب إحصائيات التبرعات: {e}")
        return {
            "total_stars": 0,
            "donors_count": 0,
            "donations_count": 0,
            "recent": []
        }

# تنفيذ إنشاء الجداول تلقائياً
init_db()
def get_image_info(image_path):
    """الحصول على معلومات الصورة"""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            info = {
                "width": img.width,
                "height": img.height,
                "format": img.format,
                "mode": img.mode,
                "size": os.path.getsize(image_path),
                "size_mb": round(os.path.getsize(image_path) / (1024 * 1024), 2)
            }
        return info
    except Exception as e:
        logging.error(f"❌ خطأ في جلب معلومات الصورة: {e}")
        return None
