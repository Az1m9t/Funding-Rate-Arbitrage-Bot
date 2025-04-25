import asyncio
import logging

import aiofiles
import aiohttp
import aiosqlite
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp_socks import ProxyConnector
from typing import List, Type, Dict
from decimal import Decimal
from bitget import BitgetFundingRateFetcher, load_data
from gate import GateFundingRateFetcher
from mexc import MexcFundingRateFetcher
from ourbit import OurbitFundingRateFetcher
from BingX import BingXFundingRateFetcher
from Bybit import BybitFundingRateFetcher
from aevo import AevoFundingRateFetcher
from hyperliquid import HyperFundingRateFetcher
from kucoin import KucoinFundingRateFetcher
from okx import OkxFundingRateFetcher
from datetime import datetime

TOKEN = ""
storage = MemoryStorage()
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()
router = Router()

# Инициализация базы данных
async def add_user(user_id: int):
    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def get_users():
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()
        return [row[0] for row in users]

async def add_to_blacklist(symbol: str):
    timestamp = int(time.time()) + 40 * 60
    async with aiosqlite.connect("users.db") as db:
        await db.execute("INSERT OR REPLACE INTO blacklist (symbol, timestamp) VALUES (?, ?)", (symbol, timestamp))
        await db.commit()

async def remove_expired_blacklist():
    current_time = int(time.time())
    async with aiosqlite.connect("users.db") as db:
        await db.execute("DELETE FROM blacklist WHERE timestamp <= ?", (current_time,))
        await db.commit()

async def get_blacklisted_symbols():
    async with aiosqlite.connect("users.db") as db:
        cursor = await db.execute("SELECT symbol FROM blacklist")
        blacklisted = await cursor.fetchall()
        return [row[0] for row in blacklisted]


async def init_db():
    async with aiosqlite.connect("settings.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                spread_low DECIMAL DEFAULT 0.3,
                spread_medium DECIMAL DEFAULT 0.7,
                spread_high DECIMAL DEFAULT 1.0,
                price_diff DECIMAL DEFAULT 1.0,
                chat_spread_low INTEGER DEFAULT 10,
                chat_spread_medium INTEGER DEFAULT 5,
                chat_spread_high INTEGER DEFAULT 0
            )
        """)
        await db.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")
        await db.commit()




async def get_settings():
    async with aiosqlite.connect("settings.db") as db:
        cursor = await db.execute(
            "SELECT spread_low, spread_medium, spread_high, price_diff, chat_spread_low, chat_spread_medium, chat_spread_high FROM settings WHERE id=1"
        )
        settings = await cursor.fetchone()
        return settings



async def update_setting(setting: str, value):
    async with aiosqlite.connect("settings.db") as db:
        await db.execute(f"UPDATE settings SET {setting} = ? WHERE id=1", (float(value),))
        await db.commit()



class SettingsState(StatesGroup):
    waiting_for_value = State()


@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.chat.id
    thread_id = message.message_thread_id
    print(user_id, thread_id)
    await add_user(message.chat.id)

@dp.message(Command("settings"))
async def settings(message: Message):
    spread_low, spread_medium, spread_high, price_diff, chat_low, chat_medium, chat_high = await get_settings()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Спред (малый): {spread_low}", callback_data="set_spread_low")],
        [InlineKeyboardButton(text=f"Спред (средний): {spread_medium}", callback_data="set_spread_medium")],
        [InlineKeyboardButton(text=f"Спред (высокий): {spread_high}", callback_data="set_spread_high")],
        [InlineKeyboardButton(text=f"Процент разницы цен: {spread_high}", callback_data="set_price_diff")],
    ])
    await message.answer("⚙ Настройки Бота:", reply_markup=keyboard)


@dp.callback_query()
async def process_callback(callback_query: CallbackQuery, state: FSMContext):
    chat_id = callback_query.message.chat.id
    thread_id = callback_query.message.message_thread_id
    print(chat_id, thread_id)
    logging.info(f"process_callback: chat_id={chat_id}, thread_id={thread_id}")

    setting_map = {
        "set_spread_low": "spread_low",
        "set_spread_medium": "spread_medium",
        "set_spread_high": "spread_high",
        "set_price_diff": "price_diff",
        "set_chat_low": "chat_spread_low",
        "set_chat_medium": "chat_spread_medium",
        "set_chat_high": "chat_spread_high"
    }
    setting = setting_map.get(callback_query.data)

    if setting:
        await state.update_data(setting=setting, chat_id=chat_id, thread_id=thread_id)
        logging.info(f"Сохранено состояние: setting={setting}, chat_id={chat_id}, thread_id={thread_id}")
        await bot.send_message(
            chat_id, f"Введите новое значение для {setting}:",
            message_thread_id=thread_id if thread_id else None, parse_mode=ParseMode.HTML
        )
        await state.set_state(SettingsState.waiting_for_value)



@dp.message(SettingsState.waiting_for_value)
async def set_new_value(message: Message, state: FSMContext):
    print(f"Получено сообщение от {message.chat.id} (thread_id={message.message_thread_id}): {message.text}")

    data = await state.get_data()
    setting = data.get("setting")
    chat_id = data.get("chat_id")
    thread_id = data.get("thread_id")

    print(f"Сохраненные данные: setting={setting}, chat_id={chat_id}, thread_id={thread_id}")

    if not setting or not chat_id:
        logging.warning("Ошибка! Не найдены настройки или chat_id.")
        return

    try:
        new_value = Decimal(message.text) if "spread" in setting else int(message.text)
        await update_setting(setting, new_value)

        print(f"Обновление {setting} в чате {chat_id} (thread_id={thread_id}): {new_value}")

        await bot.send_message(
            chat_id,
            f"✅ Значение {setting} изменено на {new_value}",
            message_thread_id=thread_id if thread_id else None, parse_mode=ParseMode.HTML
        )
    except ValueError:
        print(f"Ошибка преобразования значения: {message.text}")
        await bot.send_message(chat_id, "❌ Ошибка! Введите корректное значение.", message_thread_id=thread_id)

    await state.clear()



async def send_alert(message: str, spread_value: Decimal):
    """ Отправка уведомлений о спредах в нужные чаты """
    settings = await get_settings()
    spread_low, spread_medium, spread_high, price_diff, chat_low, chat_medium, chat_high = settings
    if spread_low <= spread_value < spread_medium:
        await bot.send_message(chat_id='-1002372495146', text=message, message_thread_id=265, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    elif spread_medium <= spread_value < spread_high:
        await bot.send_message(chat_id='-1002372495146', text=message, message_thread_id=267, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    elif spread_value >= spread_high:
        await bot.send_message(chat_id='-1002372495146', text=message, message_thread_id=269, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        logging.warning("Нет подходящего чата для отправки сообщения")

async def send_direct_alert(message: str):
    users = await get_users()
    if not users:
        logging.warning("Нет подписанных пользователей, сообщение не отправляется.")
        return

    tasks = [asyncio.create_task(bot.send_message(chat_id=user_id, text=message)) for user_id in users]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for user_id, result in zip(users, results):
        if isinstance(result, Exception):
            logging.error(f"Ошибка отправки сообщения пользователю {user_id}: {result}")
        else:
            logging.info(f"Сообщение отправлено пользователю {user_id}")



EXCHANGE_URLS = {
    "Bitget": "https://www.bitget.com/en/futures/contract/{symbol}_USDT",
    "Gate": "https://www.gate.io/ru/futures/USDT/{symbol}_USDT",
    "MEXC": "https://www.mexc.com/exchange/{symbol}_USDT",
    "ourbit": "https://www.ourbit.com/exchange/{symbol}_USDT",
    "BingX": "https://www.BingX.com/exchange/{symbol}_USDT",
    "Bybit": "https://www.Bybit.com/exchange/{symbol}_USDT",
    "aevo": "https://www.aevo.com/exchange/{symbol}_USDT",
    "okx": "https://www.okx.com/exchange/{symbol}_USDT",
}


@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.chat.id
    thread_id = message.message_thread_id
    print(user_id, thread_id)
    await add_user(user_id)

async def fetch_rates(exchange_cls: Type, symbols: List[str], proxies: List[str]):
    tasks = []
    results = []
    batch_size = 20
    logging.info(f"Запрос данных для {exchange_cls.__name__} по символам: {symbols}")

    async with aiohttp.ClientSession() as session_no_proxy:
        async with aiohttp.ClientSession() as session_proxy:
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                logging.info(f"Обрабатываем пакет: {batch}")

                tasks = []
                for j, symbol in enumerate(batch):
                    if j < 10:
                        tasks.append(exchange_cls(symbol).fetch_funding_rate(session_no_proxy))
                    else:
                        tasks.append(exchange_cls(symbol).fetch_funding_rate(session_proxy))

                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                results.extend(batch_results)
                logging.info(f"Завершена обработка пакета. Ожидание 2 секунды...")
                await asyncio.sleep(2)

    logging.info(f"Результаты запроса {exchange_cls.__name__}: {results}")
    return results

async def parse_decimal(value, exchange, field):
    if value in [None, "Not supported", "", "null"]:
        return None
    try:
        return Decimal(value)
    except Exception as e:
        return None


async def async_load_withdrawable_symbols(exchange: str) -> set:
    """Асинхронно загружает список монет, доступных к выводу с биржи."""
    file_name = f"withdrawable_{exchange}.txt"

    try:
        async with aiofiles.open(file_name, "r", encoding="utf-8") as file:
            content = await file.read()
            return {line.strip().upper() for line in content.splitlines() if line.strip()}
    except FileNotFoundError:
        logging.warning(f"Файл {file_name} не найден, считаем, что вывод недоступен для всех монет.")
        return set()

exchange_links = {
    "BingX": "https://bingx.com/en/perpetual/{symbol}-USDT/",
    "MEXC": "https://futures.mexc.com/exchange/{symbol}_USDT",
    "Bitget": "https://www.bitget.com/ru/futures/usdt/{symbol}USDT",
    "Gate": "https://www.gate.io/futures/USDT/{symbol}_USDT",
    "ourbit": "https://futures.ourbit.com/exchange/{symbol}_USDT",
    "Bybit": "https://www.bybit.com/trade/usdt/{symbol}USDT",
    "aevo": "https://app.aevo.xyz/perpetual/{symbol}",
    "Hyperliquid": "https://app.hyperliquid.xyz/trade/{symbol}",
    "kucoin": "https://www.kucoin.com/futures/trade/{symbol}USDTM",
    "okx": "https://www.okx.com/trade-swap/{symbol}-USDT-SWAP"
}

# Формирование ссылок для бирж
def get_exchange_link(exchange, symbol):
    symbol_url = symbol.replace('_USDT', '').replace('USDT', '')
    if exchange in exchange_links:
        return f'<a href="{exchange_links[exchange].format(symbol=symbol_url)}">{exchange}</a>'
    return exchange

async def main():
    await remove_expired_blacklist()
    blacklisted_symbols = await get_blacklisted_symbols()
    symbols = [s for s in load_data("coins.txt") if s not in blacklisted_symbols]
    proxies = load_data("proxies.txt")

    logging.info("Начинаем сбор данных с бирж...")

    exchanges = [BitgetFundingRateFetcher, GateFundingRateFetcher, MexcFundingRateFetcher, OurbitFundingRateFetcher, BingXFundingRateFetcher, BybitFundingRateFetcher, AevoFundingRateFetcher, OkxFundingRateFetcher]
    tasks = [fetch_rates(exchange, symbols, proxies) for exchange in exchanges]

    hyperliquidfetcher = HyperFundingRateFetcher(symbols)
    kucoinfetcher = KucoinFundingRateFetcher(symbols)
    async with aiohttp.ClientSession() as session:
        hyperliquid_data = await hyperliquidfetcher.fetch_funding_rate(session)
        kucoin_data = await kucoinfetcher.fetch_funding_rate(session)

    results = await asyncio.gather(*tasks)
    logging.info("Полученные данные от бирж:")
    for result in results:
        logging.info(result)

    symbol_rates: Dict[str, Dict[str, Decimal]] = {}
    symbol_prices: Dict[str, Dict[str, Decimal]] = {}

    for bitget, gate, mexc, ourbit, BingX, Bybit, aevo, okx in zip(*results):
        if bitget is None or not isinstance(bitget, dict):
            logging.error(f"Ошибка получения данных с Bitget: {bitget}")
            continue
        if gate is None or not isinstance(gate, dict):
            logging.error(f"Ошибка получения данных с Gate: {gate}")
            continue
        if mexc is None or not isinstance(mexc, dict):
            logging.error(f"Ошибка получения данных с MEXC: {mexc}")
            continue
        if ourbit is None or not isinstance(ourbit, dict):
            logging.error(f"Ошибка получения данных с ourbit: {ourbit}")
            continue
        if BingX is None or not isinstance(BingX, dict):
            logging.error(f"Ошибка получения данных с BingX: {BingX}")
            continue
        if Bybit is None or not isinstance(Bybit, dict):
            logging.error(f"Ошибка получения данных с Bybit: {Bybit}")
            continue
        if aevo is None or not isinstance(aevo, dict):
            logging.error(f"Ошибка получения данных с aevo: {aevo}")
            continue
        if okx is None or not isinstance(okx, dict):
            logging.error(f"Ошибка получения данных с okx: {okx}")
            continue

        symbol = bitget.get("symbol", "UNKNOWN").replace("_", "").upper()
        if symbol in blacklisted_symbols:
            continue
        try:
            rates = {
                "Bitget": await parse_decimal(bitget.get("fundingRate"), "Bitget", "fundingRate"),
                "Gate": await parse_decimal(gate.get("fundingRate"), "Gate", "fundingRate"),
                "MEXC": await parse_decimal(mexc.get("fundingRate"), "MEXC", "fundingRate"),
                "ourbit": await parse_decimal(ourbit.get("fundingRate"), "ourbit", "fundingRate"),
                "BingX": await parse_decimal(BingX.get("fundingRate"), "BingX", "fundingRate"),
                "Bybit": await parse_decimal(Bybit.get("fundingRate"), "Bybit", "fundingRate"),
                "aevo": await parse_decimal(aevo.get("fundingRate"), "aevo", "fundingRate"),
                "okx": await parse_decimal(okx.get("fundingRate"), "okx", "fundingRate"),
            }

            prices = {
                "Bitget": await parse_decimal(bitget.get("price"), "Bitget", "price"),
                "Gate": await parse_decimal(gate.get("price"), "Gate", "price"),
                "MEXC": await parse_decimal(mexc.get("price"), "MEXC", "price"),
                "ourbit": await parse_decimal(ourbit.get("price"), "ourbit", "price"),
                "BingX": await parse_decimal(BingX.get("price"), "BingX", "price"),
                "Bybit": await parse_decimal(Bybit.get("price"), "Bybit", "price"),
                "aevo": await parse_decimal(aevo.get("price"), "aevo", "price"),
                "okx": await parse_decimal(okx.get("price"), "okx", "price"),
            }


            hyperliquid_entry = next((entry for entry in hyperliquid_data if entry["symbol"] == symbol), None)
            if hyperliquid_entry:
                rates["Hyperliquid"] = await parse_decimal(hyperliquid_entry["fundingRate"], "Hyperliquid",
                                                           "fundingRate")
                prices["Hyperliquid"] = await parse_decimal(hyperliquid_entry["price"], "Hyperliquid", "price")

            kucoin_entry = next((entry for entry in kucoin_data if entry["symbol"] == symbol), None)
            if kucoin_entry:
                rates["kucoin"] = await parse_decimal(kucoin_entry["fundingRate"], "kucoin",
                                                           "fundingRate")
                prices["kucoin"] = await parse_decimal(kucoin_entry["price"], "kucoin", "price")

        except Exception as e:
                logging.error(f"Ошибка при обработке данных для {symbol}: {e} {bitget.get('fundingRate'), gate.get('fundingRate'), mexc.get('fundingRate'), ourbit.get('fundingRate'), BingX.get('fundingRate'), Bybit.get('fundingRate'), aevo.get('fundingRate'), okx.get('fundingRate')}")
                continue

        symbol_rates[symbol] = rates
        symbol_prices[symbol] = prices

    max_spreads = {}  # Словарь для хранения информации о максимальном спреде для каждой монеты

    for symbol, rates in symbol_rates.items():
        exchanges = list(rates.keys())
        for i in range(len(exchanges)):
            for j in range(i + 1, len(exchanges)):
                ex1, ex2 = exchanges[i], exchanges[j]
                rate1, rate2 = rates[ex1], rates[ex2]
                price1, price2 = symbol_prices[symbol][ex1], symbol_prices[symbol][ex2]

                if rate1 is None or rate2 is None:
                    continue

                settings = await get_settings()
                spread_low, spread_medium, spread_high, price_diff, chat_low, chat_medium, chat_high = settings

                spread = abs(rate1 - rate2)
                price_diff_percent = abs((price1 - price2) / min(price1, price2) * 100) if min(price1,
                                                                                               price2) > 0 else 100

                if spread > Decimal(spread_low) and price_diff_percent <= float(price_diff):
                    if symbol not in max_spreads or spread > max_spreads[symbol]["spread"]:
                        max_spreads[symbol] = {
                            "spread": spread,
                            "ex1": ex1,
                            "ex2": ex2,
                            "rate1": rate1,
                            "rate2": rate2,
                            "price1": price1,
                            "price2": price2,
                            "price_diff_percent": price_diff_percent
                        }

    # Отправляем только одно уведомление для каждой монеты с максимальным спредом
    for symbol, data in max_spreads.items():
        await add_to_blacklist(symbol)
        ex1, ex2 = data["ex1"], data["ex2"]
        rate1, rate2 = data["rate1"], data["rate2"]
        price1, price2 = data["price1"], data["price2"]
        price_diff_percent = data["price_diff_percent"]

        withdrawable_ex1, withdrawable_ex2 = await asyncio.gather(
            async_load_withdrawable_symbols(ex1),
            async_load_withdrawable_symbols(ex2)
        )
        can_withdraw_ex1 = symbol in withdrawable_ex1 if withdrawable_ex1 else True
        can_withdraw_ex2 = symbol in withdrawable_ex2 if withdrawable_ex2 else True

        withdraw_status = {
            ex1: " Вывод: ✅" if can_withdraw_ex1 else " Вывод: ❌",
            ex2: " Вывод: ✅" if can_withdraw_ex2 else " Вывод: ❌"
        }

        symbol_print = symbol.replace('_USDT', '').replace('USDT', '')

        ex1_risk = get_exchange_link(ex1, symbol)
        ex2_risk = get_exchange_link(ex2, symbol)

        if ex1 == 'ourbit':
            ex1_risk += ' - 🚩 high risk'
        if ex2 == 'ourbit':
            ex2_risk += ' - 🚩 high risk'

        # Получение истории фандинга для выбранных бирж
        history_data = {}
        fetchers = {
            "Bitget": BitgetFundingRateFetcher(symbol),
            "Gate": GateFundingRateFetcher(symbol),
            "MEXC": MexcFundingRateFetcher(symbol),
            "ourbit": OurbitFundingRateFetcher(symbol),
            "BingX": BingXFundingRateFetcher(symbol),
            "Bybit": BybitFundingRateFetcher(symbol),
            "aevo": AevoFundingRateFetcher(symbol),
            "Hyperliquid": HyperFundingRateFetcher(symbol),
            "kucoin": KucoinFundingRateFetcher(symbol),
            "okx": OkxFundingRateFetcher(symbol),
        }

        async with aiohttp.ClientSession() as session:
            tasks = []
            for exchange in [ex1, ex2]:
                if exchange in fetchers:
                    tasks.append(fetchers[exchange].fetch_history_funding(symbol, session))

            results = await asyncio.gather(*tasks, return_exceptions=True)

        for exchange, result in zip([ex1, ex2], results):
            if isinstance(result, Exception):
                logging.error(f"Ошибка при получении истории {exchange} для {symbol}: {result}")
            else:
                history_data[exchange] = result
        spread = abs(rate1 - rate2)
        # Формирование уведомления
        message = (
            f"💲{symbol_print}/USDT\n\n"
            f"📊 <b>Биржи:</b> {ex1_risk} ↔️ {ex2_risk}\n\n"
            f"📈 <b>Фандинг:</b>\n\n"
            f"  {ex1}: {rate1:.4f}%\n"
            f"  {ex2}: {rate2:.4f}%\n\n"
            f"<b>Спред</b>: {spread:.5f}\n\n"
            f"💰 <b>Цена:</b>\n\n"
            f"  {ex1}: ({float(price1):.5f}$)\n"
            f"  {ex2}: ({float(price2):.5f}$)\n\n"
            f"⚖ <b>Разница цен:</b> {price_diff_percent:.2f}%\n\n"
            f"🕰 <b>История фандинга:</b>\n"
        )

        for exchange, data in history_data.items():
            message += f"\n{exchange}:\n\n"

            # Преобразуем данные в список кортежей (timestamp, rate)
            parsed_data = []
            for rate, timestamp in data.items():
                try:
                    timestamp = int(timestamp)
                    if len(str(timestamp)) == 13:
                        timestamp = timestamp // 1000  # Преобразование миллисекунд в секунды
                    parsed_data.append((timestamp, float(rate)))
                except ValueError as e:
                    logging.error(f"Ошибка при обработке timestamp {timestamp} для {exchange}: {e}")

            # Сортируем по timestamp в порядке убывания (сначала самые новые)
            parsed_data.sort(reverse=True, key=lambda x: x[0])

            # Формируем сообщение
            for timestamp, rate in parsed_data:
                formatted_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                message += f"{rate:.4f}% ({formatted_time})\n"

        logging.info(f"Отправка уведомления: {message}")
        await send_alert(message, spread)


async def monitor():
    while True:
        try:
            logging.info("Запуск основного цикла мониторинга...")
            await main()
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Ошибка в monitor(): {e}")


if __name__ == "__main__":

    dp.include_router(router)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def main_app():
        await asyncio.gather(
            init_db(),
            monitor(),
            dp.start_polling(bot)
        )

    asyncio.run(main_app())

