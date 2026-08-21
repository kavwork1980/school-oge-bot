"""Telegram-бот «Н или НН» — первая рабочая версия.

Что делает: /start → выбор темы → 5 заданий → ответ и объяснение после
каждого → итог 0–5 → повторить или закончить. В любой момент /stop.

Запуск:
    python bot.py

Токен читается только из переменной окружения TELEGRAM_BOT_TOKEN
(её можно положить в локальный файл .env — он в Git не попадает).
Настоящего токена в этом файле нет и быть не должно.

Файл отвечает только за общение с Telegram. Сама логика тренировки — в
quiz.py, тексты заданий — в questions.py.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from questions import DONT_KNOW
from quiz import TOTAL, Session

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Тексты
# --------------------------------------------------------------------------

GREETING = (
    "Привет. Здесь можно потренировать одну вещь: Н или НН в словах вроде "
    "«тканая скатерть» и «брошенный мяч».\n\n"
    "После каждого ответа объясняю, почему так — не просто показываю "
    "правильную букву."
)

TOPIC_INTRO = (
    "Тема: Н и НН в отглагольных прилагательных и причастиях.\n\n"
    "Будет 5 коротких заданий. Отвечаешь одной кнопкой — Н или НН. "
    "После каждого ответа сразу говорю, верно или нет, и объясняю почему.\n\n"
    "Займёт минут пять."
)

STOP_DURING = "Остановились. Ответы этой тренировки не сохраняю.\n\nЧтобы начать заново — /start."
STOP_IDLE = "Сейчас тренировка не идёт. Чтобы начать — /start."
FINISH_TEXT = "Хорошо. Чтобы начать заново — напиши /start."
ONLY_BUTTONS = "Я понимаю только кнопки и команды /start и /stop."
NO_SESSION = "Тренировка не найдена. Начни заново: /start"
OLD_BUTTON = "Это кнопка от прошлого задания."


# --------------------------------------------------------------------------
# Кнопки
# --------------------------------------------------------------------------

def topic_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Н/НН в прилагательных и причастиях", callback_data="topic")]]
    )


def begin_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Начать", callback_data="begin")]])


def answer_keyboard(question, question_index):
    """Кнопки ответа для одного задания.

    В callback_data кладём номер задания — по нему потом видно, что кнопку
    нажали от текущего задания, а не от старого.
    """
    row = [
        InlineKeyboardButton(
            label, callback_data="ans:{}:{}".format(question_index, i)
        )
        for i, label in enumerate(question["options"])
    ]
    second_row = [
        InlineKeyboardButton(
            "Не знаю", callback_data="ans:{}:{}".format(question_index, DONT_KNOW)
        )
    ]
    return InlineKeyboardMarkup([row, second_row])


def result_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Пройти ещё раз", callback_data="again")],
            [InlineKeyboardButton("Закончить", callback_data="finish")],
        ]
    )


# --------------------------------------------------------------------------
# Работа с состоянием
#
# Состояние живёт в context.user_data — это обычный словарь в памяти процесса,
# свой у каждого пользователя. Поэтому два человека не мешают друг другу.
# При перезапуске бота состояние теряется — для первой версии это нормально.
# --------------------------------------------------------------------------

def get_session(context):
    return context.user_data.get("session")


def clear_session(context):
    context.user_data.pop("session", None)


# --------------------------------------------------------------------------
# Отправка задания
# --------------------------------------------------------------------------

async def send_question(chat, session):
    """Показать текущее задание. Если заданий больше нет — показать итог."""
    question = session.current()

    if question is None:
        await chat.send_message(session.summary(), reply_markup=result_keyboard())
        return

    text = "{} из {}\n\n{}".format(session.number(), TOTAL, question["text"])
    await chat.send_message(text, reply_markup=answer_keyboard(question, session.index))


# --------------------------------------------------------------------------
# Команды
# --------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — работает всегда, в том числе посреди незаконченной тренировки.

    Незаконченная тренировка при этом просто сбрасывается.
    """
    clear_session(context)
    await update.message.reply_text(GREETING, reply_markup=topic_keyboard())


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stop — работает на любом шаге, в том числе до начала тренировки."""
    had_session = get_session(context) is not None
    clear_session(context)
    await update.message.reply_text(STOP_DURING if had_session else STOP_IDLE)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любое обычное сообщение или неизвестная команда."""
    await update.message.reply_text(ONLY_BUTTONS)


# --------------------------------------------------------------------------
# Нажатия кнопок
# --------------------------------------------------------------------------

async def on_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.chat.send_message(TOPIC_INTRO, reply_markup=begin_keyboard())


async def on_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало тренировки: счёт обнуляется, показывается первое задание."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    context.user_data["session"] = Session()
    await send_question(query.message.chat, context.user_data["session"])


async def on_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    session = get_session(context)
    if session is None:
        await query.answer()
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.chat.send_message(NO_SESSION)
        return

    # callback_data выглядит так: "ans:2:1" — задание 2, кнопка 1.
    _, raw_index, raw_option = query.data.split(":")
    question_index = int(raw_index)
    option_index = int(raw_option)

    result = session.submit(question_index, option_index)

    if result is None:
        # Старая кнопка или второе нажатие подряд. Балл не начисляем.
        await query.answer(OLD_BUTTON)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    await query.answer()
    # Убираем кнопки у отвеченного задания, чтобы на них нельзя было нажать снова.
    await query.edit_message_reply_markup(reply_markup=None)

    if result.is_dont_know:
        head = "Правильный ответ: {}.".format(result.answer_text)
    elif result.is_correct:
        head = "Верно. Правильный ответ: {}.".format(result.answer_text)
    else:
        head = "Неверно. Правильный ответ: {}.".format(result.answer_text)

    await query.message.chat.send_message("{}\n\n{}".format(head, result.explanation))
    await send_question(query.message.chat, session)


async def on_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Новая тренировка после итога: счёт начинается с нуля."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    context.user_data["session"] = Session()
    await send_question(query.message.chat, context.user_data["session"])


async def on_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    clear_session(context)
    await query.message.chat.send_message(FINISH_TEXT)


# --------------------------------------------------------------------------
# Запуск
# --------------------------------------------------------------------------

def read_token():
    """Прочитать токен из окружения. Без токена бот не запускается."""
    # Читаем .env только из папки этого проекта. Без указания пути dotenv
    # ищет .env ещё и в папках выше и может подхватить чужой файл.
    project_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(project_dir, ".env"))

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    if not token or token == "put_your_token_here":
        raise SystemExit(
            "Не найден TELEGRAM_BOT_TOKEN.\n"
            "Скопируй .env.example в .env и впиши туда токен от @BotFather."
        )
    return token


def main():
    application = Application.builder().token(read_token()).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("stop", cmd_stop))

    application.add_handler(CallbackQueryHandler(on_topic, pattern=r"^topic$"))
    application.add_handler(CallbackQueryHandler(on_begin, pattern=r"^begin$"))
    application.add_handler(CallbackQueryHandler(on_answer, pattern=r"^ans:"))
    application.add_handler(CallbackQueryHandler(on_again, pattern=r"^again$"))
    application.add_handler(CallbackQueryHandler(on_finish, pattern=r"^finish$"))

    # Должен идти последним: ловит и обычный текст, и неизвестные команды.
    application.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, on_text))

    logger.info("Бот запущен. Остановить — Ctrl+C.")
    application.run_polling()


if __name__ == "__main__":
    main()
