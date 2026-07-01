from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# القائمة الرئيسية
def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("📸 تحسين الصورة")],
        [KeyboardButton("✨ تحسين متقدم"), KeyboardButton("🚀 تحسين فائق")],
        [KeyboardButton("📊 إحصائياتي"), KeyboardButton("🛠 لوحة التحكم")],
        [KeyboardButton("⭐ تبرع 50 نجمة لدعم البوت")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# قائمة أغنيتي (تم تغييرها لقائمة تحسين الصور)
def my_song_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📸 تحسين عادي", callback_data="enhance_standard")],
        [InlineKeyboardButton("✨ تحسين متقدم", callback_data="enhance_premium")],
        [InlineKeyboardButton("🚀 تحسين فائق", callback_data="enhance_super")],
        [InlineKeyboardButton("🎯 اختيار مستوى مخصص", callback_data="enhance_custom")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(keyboard)

# قائمة اختيار الجودة (أصبحت لاختيار مستوى التحسين)
def quality_keyboard(action_type):
    keyboard = [
        [
            InlineKeyboardButton("⭐ مستوى 1", callback_data=f"level_1"),
            InlineKeyboardButton("⭐ مستوى 2", callback_data=f"level_2"),
        ],
        [
            InlineKeyboardButton("⭐ مستوى 3", callback_data=f"level_3"),
            InlineKeyboardButton("⭐ مستوى 4", callback_data=f"level_4"),
        ],
        [
            InlineKeyboardButton("⭐ مستوى 5", callback_data=f"level_5"),
        ],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(keyboard)

# لوحة تحكم الإدارة
def admin_panel_keyboard(maintenance_status):
    m_text = "🔴 إيقاف الصيانة" if maintenance_status else "🟢 تفعيل الصيانة"
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats")],
        [InlineKeyboardButton(m_text, callback_data="toggle_maintenance")],
        [InlineKeyboardButton("📢 إذاعة (Broadcast)", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🗑 تنظيف الملفات المؤقتة", callback_data="admin_clean")],
        [InlineKeyboardButton("⭐ إحصائيات التبرعات", callback_data="admin_stars_stats")],
        [InlineKeyboardButton("📢 إدارة القنوات الإجبارية", callback_data="admin_channels")],
        [InlineKeyboardButton("❌ إغلاق اللوحة", callback_data="close_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

# إدارة القنوات
def channels_management_keyboard(channels):
    keyboard = []
    
    for channel in channels:
        username = channel['channel_username']
        name = channel.get('channel_name', username)
        keyboard.append([
            InlineKeyboardButton(
                f"🗑 حذف @{username}",
                callback_data=f"channel_remove_{username}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="channel_add")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_stats")
    ])
    
    return InlineKeyboardMarkup(keyboard)

# زر إلغاء العملية
def cancel_keyboard():
    keyboard = [[InlineKeyboardButton("❌ إلغاء العملية", callback_data="cancel_action")]]
    return InlineKeyboardMarkup(keyboard)
