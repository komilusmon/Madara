# bot.py
import os
import sqlite3
import asyncio
import logging
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode

# ==================== KONFIGURATSIYA ====================
TOKEN = os.getenv("TOKEN", "8146045855:AAHxUNx0x1UtMSY3tePQvCI1TeO3Faq98bI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7075245740"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ==================== MA'LUMOTLAR BAZASI ====================
def get_db_connection():
    conn = sqlite3.connect("menubuilder.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        plan_type TEXT DEFAULT 'free',
        menus_created INTEGER DEFAULT 0,
        max_menus INTEGER DEFAULT 3,
        joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS menus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        menu_name TEXT NOT NULL,
        menu_type TEXT DEFAULT 'inline',
        menu_data TEXT NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        template_data TEXT NOT NULL,
        is_premium BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Shablonlar
    templates = [
        {
            "name": "🛍️ Online Do'kon",
            "category": "ecommerce",
            "data": {
                "type": "inline",
                "text": "🛍️ Onlayn do'konimizga xush kelibsiz!",
                "rows": [
                    [{"text": "🛍️ Mahsulotlar", "callback": "products"}],
                    [{"text": "📦 Buyurtmalar", "callback": "orders"}],
                    [{"text": "👤 Profil", "callback": "profile"}]
                ]
            },
            "premium": False
        }
    ]
    
    for template in templates:
        cursor.execute(
            "INSERT OR IGNORE INTO templates (name, category, template_data, is_premium) VALUES (?, ?, ?, ?)",
            (template["name"], template["category"], json.dumps(template["data"]), template["premium"])
        )
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

# ==================== KLAVIATURALAR ====================
def get_main_keyboard(user_id):
    if user_id == ADMIN_ID:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎨 Menyu Qurish"), KeyboardButton(text="📊 Statistika")],
                [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text="🛍️ Shablonlar")],
                [KeyboardButton(text="⚙️ Sozlamalar")]
            ],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎨 Menyu Qurish"), KeyboardButton(text="📁 Mening Menyularim")],
                [KeyboardButton(text="🛍️ Shablonlar"), KeyboardButton(text="💎 Tariflar")],
                [KeyboardButton(text="ℹ️ Yordam")]
            ],
            resize_keyboard=True
        )

def get_builder_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tugma qo'shish", callback_data="add_button")],
        [InlineKeyboardButton(text="📝 Matn qo'shish", callback_data="add_text")],
        [InlineKeyboardButton(text="👀 Ko'rish", callback_data="preview")],
        [InlineKeyboardButton(text="💾 Saqlash", callback_data="save")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")]
    ])

# ==================== HANDLERLAR ====================
user_states = {}

@router.message(CommandStart())
async def start_handler(msg: Message):
    user_id = msg.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
        (user_id, msg.from_user.username, msg.from_user.full_name)
    )
    conn.commit()
    conn.close()
    
    welcome_text = (
        "🤖 <b>MenuBuilderBot ga Xush Kelibsiz!</b>\n\n"
        "🚀 Kod yozmasdan Telegram bot menyularingizni yarating!\n\n"
        "✨ <b>Xususiyatlar:</b>\n"
        "• 🎨 Visual menyu qurish\n"
        "• 🛍️ Tayyor shablonlar\n"
        "• 💎 Premium funksiyalar\n"
        "• 📱 Mobile optimallashtirilgan"
    )
    
    await msg.answer(welcome_text, reply_markup=get_main_keyboard(user_id))

@router.message(F.text == "🎨 Menyu Qurish")
async def start_builder(msg: Message):
    user_id = msg.from_user.id
    
    user_states[user_id] = {
        "step": "waiting_name",
        "menu": {"name": "", "text": "Salom! Menyu tanlang:", "rows": [[]]}
    }
    
    await msg.answer(
        "🎨 <b>Menyu Qurish</b>\n\n"
        "Avval menyu nomini kiriting:\n"
        "Masalan: <code>Asosiy menyu</code>"
    )

@router.message(F.text == "📁 Mening Menyularim")
async def my_menus(msg: Message):
    user_id = msg.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT menu_name, created_at FROM menus WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    )
    menus = cursor.fetchall()
    conn.close()
    
    if not menus:
        await msg.answer("📭 Hozircha menyu mavjud emas")
        return
    
    text = "📁 <b>Mening Menyularim:</b>\n\n"
    for menu in menus:
        text += f"• {menu['menu_name']}\n"
        text += f"  📅 {menu['created_at'][:10]}\n\n"
    
    await msg.answer(text)

@router.message(F.text == "🛍️ Shablonlar")
async def templates(msg: Message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM templates")
    templates_list = cursor.fetchall()
    conn.close()
    
    keyboard = []
    for template in templates_list:
        keyboard.append([InlineKeyboardButton(text=template['name'], callback_data=f"template_{template['name']}")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")])
    
    await msg.answer(
        "🛍️ <b>Shablonlar:</b>\n\n"
        "Quyidagi shablonlardan birini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.message(F.text == "📊 Statistika")
async def stats(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM menus")
    total_menus = cursor.fetchone()[0]
    
    conn.close()
    
    text = (
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Foydalanuvchilar: {total_users}\n"
        f"📁 Menyular: {total_menus}\n"
        f"🕐 Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    await msg.answer(text)

# ==================== CALLBACK HANDLERLAR ====================
@router.callback_query(F.data == "add_button")
async def add_button(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_states:
        await callback.answer("❌ Menyu qurish boshlanmagan!")
        return
    
    user_states[user_id]["step"] = "adding_button"
    await callback.message.answer("➕ Tugma matnini kiriting:")
    await callback.answer()

@router.callback_query(F.data == "preview")
async def preview_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_states:
        await callback.answer("❌ Menyu qurish boshlanmagan!")
        return
    
    menu = user_states[user_id]["menu"]
    
    if not menu["name"]:
        await callback.answer("❌ Menyu nomi kiritilmagan!")
        return
    
    # Preview yaratish
    keyboard = []
    for row in menu["rows"]:
        if row:
            keyboard_row = []
            for button in row:
                keyboard_row.append(InlineKeyboardButton(text=button, callback_data="preview"))
            keyboard.append(keyboard_row)
    
    await callback.message.answer(
        f"👀 <b>Preview:</b> {menu['name']}\n\n{menu['text']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
    )
    await callback.answer()

@router.callback_query(F.data == "save")
async def save_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_states:
        await callback.answer("❌ Menyu qurish boshlanmagan!")
        return
    
    menu = user_states[user_id]["menu"]
    
    if not menu["name"]:
        await callback.answer("❌ Menyu nomi kiritilmagan!")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO menus (user_id, menu_name, menu_data) VALUES (?, ?, ?)",
        (user_id, menu["name"], json.dumps(menu))
    )
    
    cursor.execute("UPDATE users SET menus_created = menus_created + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    await callback.message.answer(f"✅ <b>Menyu saqlandi:</b> {menu['name']}")
    del user_states[user_id]
    await callback.answer("✅ Saqlandi!")

# ==================== MESSAGE HANDLER ====================
@router.message()
async def process_builder(msg: Message):
    user_id = msg.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state["step"] == "waiting_name":
        state["menu"]["name"] = msg.text
        state["step"] = "building"
        await msg.answer(
            f"✅ <b>Menyu nomi:</b> {msg.text}\n\n"
            "Endi menyu qurishni boshlang:",
            reply_markup=get_builder_keyboard()
        )
    
    elif state["step"] == "adding_button":
        state["menu"]["rows"][-1].append(msg.text)
        state["step"] = "building"
        await msg.answer(
            f"✅ <b>Tugma qo'shildi:</b> {msg.text}",
            reply_markup=get_builder_keyboard()
        )

# ==================== BOSHQA HANDLERLAR ====================
@router.callback_query(F.data == "back")
async def back_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    
    await callback.message.answer("🏠 Asosiy menyu:", reply_markup=get_main_keyboard(user_id))
    await callback.answer()

async def main():
    logger.info("🤖 Bot ishga tushmoqda...")
    init_database()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
