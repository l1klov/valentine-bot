import os, sqlite3, uuid, threading, asyncio
from flask import Flask, render_template, send_from_directory
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8515518123:AAGsFUHNzIy-_Rme9WiW2r17SUNGh6eeX1M"  # <--- ВСТАВЬ ТОКЕН ТУТ
BASE_URL = "http://127.0.0.1:5000"     # <--- Пока ты на компьютере, оставь так

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect('orders.db')
    conn.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, name TEXT, photo TEXT, paid INTEGER)')
    conn.close()

class Order(StatesGroup):
    name = State()
    photo = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Привет! ❤️ Давай сделаем валентинку.\nКак зовут того, кому мы её дарим?")
    await state.set_state(Order.name)

@dp.message(Order.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Супер! Теперь пришли фото которое будет в конце.")
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
    conn.execute("INSERT INTO orders VALUES (?, ?, ?, ?)", (order_id, data['name'], f"/{photo_path}", 0))
    conn.commit()
    conn.close()

    # ОТПРАВКА СЧЕТА (ИНВОЙСА)
    await message.answer("Почти готово! Оплати 50 звезд, чтобы получить ссылку.")
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Твоя Валентинка",
        description="Доступ к секретной странице",
        payload=order_id,
        provider_token="", # Для звезд это поле должно быть пустым!
        currency="XTR",
        prices=[types.LabeledPrice(label="Оплата", amount=50)]
    )
    await state.clear()

# ОБЯЗАТЕЛЬНО: Подтверждение перед оплатой
@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

# Успешная оплата
@dp.message(F.successful_payment)
async def on_success(message: types.Message):
    order_id = message.successful_payment.invoice_payload
    conn = sqlite3.connect('orders.db')
    conn.execute("UPDATE orders SET paid = 1 WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    await message.answer(f"✅ Оплачено! Твоя ссылка:\n{BASE_URL}/v/{order_id}")

@app.route('/v/<order_id>')
def view_valentine(order_id):
    conn = sqlite3.connect('orders.db')
    order = conn.execute("SELECT name, photo FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    if order: return render_template('index.html', name=order[0], photo_url=order[1])
    return "Не найдено", 404

def run_flask():
    app.run(host='0.0.0.0', port=5000)

async def main():
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
