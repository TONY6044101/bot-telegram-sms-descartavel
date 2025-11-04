import asyncio
import logging
import requests
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from config import TG_TOKEN, SMSACTIVATE_KEY, PLUGGY_LINK, PLUGGY_WEBHOOK_SECRET, DB_PATH
from database import saldo, atualiza_saldo, init_db

bot = Bot(token=TG_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

PRICES = {"Brasil": (15, 0.60), "EUA": (1, 1.00), "RU": (0, 2.50)}

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    atualiza_saldo(msg.from_user.id, 0, "cadastro", "-")
    await msg.answer(
        "<b>Bot SMS descartável</b>\n"
        "Comandos: /depositar /saldo /comprar\n"
        "Depósito mínimo: R$1.00\n"
        "Preços: Brasil R$0,60 | EUA R$1,00 | Rússia R$2,50"
    )

@dp.message_handler(commands=["saldo"])
async def saldo_cmd(msg: types.Message):
    s = saldo(msg.from_user.id)
    await msg.answer(f"Seu saldo: <b>R$ {s:.2f}</b>")

@dp.message_handler(commands=["depositar"])
async def depositar(msg: types.Message):
    await msg.answer(f"Deposite via: {PLUGGY_LINK}\nMínimo R$1.00 (envie seu comprovante caso haja atraso)")

@dp.message_handler(commands=["comprar"])
async def comprar(msg: types.Message):
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for p in PRICES: menu.add(p)
    await msg.answer("Escolha o país:", reply_markup=menu)

@dp.message_handler(lambda m: m.text in PRICES)
async def pega_numero(msg: types.Message):
    uid = msg.from_user.id
    pais, (country_id, preco) = msg.text, PRICES[msg.text]
    if saldo(uid) < preco:
        await msg.answer("Saldo insuficiente.")
        return
    r = requests.get(
        f"https://sms-activate.org/stubs/handler_api.php?api_key={SMSACTIVATE_KEY}&action=getNumber&country={country_id}&service=ot"
    )
    if r.text.startswith("ACCESS_NUMBER"):
        _, idreq, num = r.text.strip().split(":")
        atualiza_saldo(uid, -preco, "compra", f"Num:{num}")
        await msg.answer(f"<b>Seu número:</b>\n{num}\nAguarde aqui o código SMS...")
        asyncio.create_task(busca_sms(uid, idreq))
    else:
        await msg.answer("Indisponível no momento. Tente novamente.")

async def busca_sms(uid, idreq):
    for _ in range(60):  # 5 min
        resp = requests.get(
            f"https://sms-activate.org/stubs/handler_api.php?api_key={SMSACTIVATE_KEY}&action=getStatus&id={idreq}"
        )
        if "STATUS_OK" in resp.text:
            codigo = resp.text.split(":")[-1]
            await bot.send_message(uid, f"<b>Código SMS:</b> <code>{codigo}</code>")
            return
        await asyncio.sleep(5)
    await bot.send_message(uid, "Tempo esgotado para receber o código.")

if __name__ == "__main__":
    init_db()
    executor.start_polling(dp)