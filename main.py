import os
import sqlite3
import uuid
import threading
import asyncio
from flask import Flask, render_template
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
# Если запускаешь на ПК — вставь токен сюда. На Render он возьмется из Environment Variables.
BOT_TOKEN = os.getenv("8515518123:AAGsFUHNzIy-_Rme9WiW2r17SUNGh6eeX1M") 
BASE_URL = os.getenv("https://valentine-bot-elch.onrender.com")

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders 
                      (id TEXT PRIMARY KEY, user_id INTEGER, name TEXT, photo TEXT, paid INTEGER)''')
    cursor.execute("PRAGMA table_info(orders)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER")
    conn.commit()
    conn.close()

class Order(StatesGroup):
    name = State()
    photo = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Привет! ❤️ Давай создадим валентинку.\nКак зовут твою половинку?")
    await state.set_state(Order.name)

@dp.message(Command("my_link"))
async def cmd_my_link(message: types.Message):
    conn = sqlite3.connect('orders.db')
    order = conn.execute("SELECT id FROM orders WHERE user_id = ? AND paid = 1 ORDER BY ROWID DESC LIMIT 1", 
                         (message.from_user.id,)).fetchone()
    conn.close()
    if order:
        await message.answer(f"Твоя ссылка:\n{BASE_URL}/v/{order[0]}")
    else:
        await message.answer("У тебя пока нет оплаченных валентинок. Нажми /start!")

@dp.message(Order.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Супер! Теперь пришли фото.")
    await state.set_state(Order.photo)

@dp.message(Order.photo, F.photo)
async def get_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = str(uuid.uuid4())[:8]
    if not os.path.exists('static'): os.makedirs('static')
    
    photo = message.photo[-1]
    photo_path = f"static/{order_id}.jpg"
    await bot.download(photo, destination=photo_path)

    conn = sqlite3.connect('orders.db')
    conn.execute("INSERT INTO orders (id, user_id, name, photo, paid) VALUES (?, ?, ?, ?, ?)", 
                 (order_id, message.from_user.id, data['name'], f"/{photo_path}", 0))
    conn.commit()
    conn.close()

    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Валентинка для " + data['name'],
        description="Оплата доступа (50 звезд)",
        payload=order_id,
        provider_token="", 
        currency="XTR",
        prices=[types.LabeledPrice(label="Оплата", amount=50)]
    )
    await state.clear()

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def on_success(message: types.Message):
    order_id = message.successful_payment.invoice_payload
    conn = sqlite3.connect('orders.db')
    conn.execute("UPDATE orders SET paid = 1 WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    await message.answer(f"🎉 Готово! Ссылка:\n{BASE_URL}/v/{order_id}")

@app.route('/')
def home():
    return "Бот работает! Перейдите в Telegram."

@app.route('/v/<order_id>')
def view_valentine(order_id):
    conn = sqlite3.connect('orders.db')
    order = conn.execute("SELECT name, photo FROM orders WHERE id = ? AND paid = 1", (order_id,)).fetchone()
    conn.close()
    if order:
        return render_template('index.html', name=order[0], photo_url=order[1])
    return "Не найдено", 404

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

async def main():
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

