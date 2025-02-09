import asyncio
import os
import logging
from decouple import config
import aiosqlite

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties

# basic vars
api_token = config("API")
admin_id = config("ADMIN_ID")
bot = Bot(token=api_token, default=DefaultBotProperties(
    parse_mode="HTML"
))
dp = Dispatcher()

# states
class bot_states(StatesGroup):
    message = State()
    question = State()
    pasta = State()

# class with most used things
class usings:
    # for start handlers
    # texts
    def start_text(username):
        return f"🤖 Привет, {username}, выбери пункт из списка:"
    # start keyboard
    send_msg_button = InlineKeyboardButton(text="✉️ Отправить сообщение", callback_data="msg_button")
    send_ques_button = InlineKeyboardButton(text="📝 Оставить вопрос", callback_data="ques_button")
    send_pasta_button = InlineKeyboardButton(text="🍝 Прислать пасту для @sovam_copypasta", callback_data="pasta_button")
    start_markup = InlineKeyboardMarkup(inline_keyboard=[[send_msg_button, send_ques_button], [send_pasta_button]])

    # for send handlers
    # texts
    send_msg_text = "📎 Отправь сообщение или вложение:"
    send_ques_text = "❓Отправь сообщение, содержащие вопрос, и через некоторое время получишь ответ:"
    send_pasta_text = "📬 Отправь пасту, чтобы она была опубликована в <a href=\"https://t.me/sovam_copypasta\">канале с пастами</a>. Не приветствуются пасты длиннее 3 строк."
    # cancel keyboard
    cancel_button = InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    cancel_markup = InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])
    # after sending keyboard
    def after_send(button_callback_data):
        send_again_msg_button = InlineKeyboardButton(text="🔄 Отправить ещё", callback_data=button_callback_data)
        return_button = InlineKeyboardButton(text="↩️ Вернутся", callback_data="cancel")
        markup = InlineKeyboardMarkup(inline_keyboard=[[return_button, send_again_msg_button]])
        return markup
    # remove cancel button
    async def rem_cancel_button(message, state, text):
        data = await state.get_data()
        message_id = data.get("message")
        await bot.edit_message_text(text=text, chat_id=message.chat.id, message_id=message_id)

# work with sqlite
# initiation database
async def setup_db():
    async with aiosqlite.connect("main.db") as connection:
        await connection.execute('''
        CREATE TABLE IF NOT EXISTS Questions (
            sended_message_id INTEGER PRIMARY KEY,
            sender_chat_id INTEGER NOT NULL,
            sender_message_id INTEGER NOT NULL
        )
        ''')
        await connection.commit()
# write question information to send reply on it
async def write_question_data(sended_message_id, sender_chat_id, sender_message_id):
    async with aiosqlite.connect("main.db") as connection:
        await connection.execute("INSERT INTO Questions (sended_message_id, sender_chat_id, sender_message_id) VALUES (?, ?, ?)",
                                 (sended_message_id, sender_chat_id, sender_message_id))
        await connection.commit()
# return information about where to send reply and clear it
async def get_question_data(sended_message_id):
    async with aiosqlite.connect("main.db") as connection:
        async with connection.execute("SELECT sender_chat_id, sender_message_id FROM Questions WHERE sended_message_id = ?",
                                        (sended_message_id,)) as cursor:
            row = await cursor.fetchone()
        await connection.execute("DELETE FROM Questions WHERE sended_message_id = ?", (sended_message_id,))
        await connection.commit()
        return row

# start command
@dp.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext):
    # clearing states to avoid bugs
    await state.set_state(None)
    # sending start message
    await message.answer(text=usings.start_text(message.from_user.full_name), reply_markup=usings.start_markup)

# return to main menu after cancelling action
@dp.callback_query(F.data == "cancel")
async def cancel_handle(callback_query: CallbackQuery, state: FSMContext):
    # clearing states to avoid bugs
    await state.set_state(None)
    # answering callback query and return message to main menu
    await callback_query.answer()
    await callback_query.message.edit_text(text=usings.start_text(callback_query.from_user.full_name), reply_markup=usings.start_markup)

# send pseudonimous message
@dp.callback_query(F.data == "msg_button")
async def msg_handle(callback_query: CallbackQuery, state: FSMContext):
    # answering callback query and edit message
    await callback_query.answer()
    await callback_query.message.edit_text(text=usings.send_msg_text, reply_markup=usings.cancel_markup)
    # set state to receive message
    await state.set_state(bot_states.message)
    # saving message id to remove cancel button in future
    await state.update_data(message = callback_query.message.message_id)

# processing pseudonimous message
@dp.message(bot_states.message)
async def msg_handle_process(message: types.Message, state: FSMContext):
    # send pseгdonimous message to admin
    await bot.send_message(chat_id=admin_id, text=f"Было получено сообщение от @{message.from_user.username}:")
    await message.send_copy(chat_id=admin_id)
    # send success message to sender
    await message.answer(text="✅ Ваше сообщение было отправлено успешно!", reply_markup=usings.after_send(button_callback_data="msg_button"))
    # removing cancel button
    await usings.rem_cancel_button(message=message, state=state, text=usings.send_msg_text)
    # clearing state
    await state.set_state(None)

# send pseudonimous qustion
@dp.callback_query(F.data == "ques_button")
async def ques_handle(callback_query: CallbackQuery, state: FSMContext):
    # answering callback query and edit message
    await callback_query.answer()
    await callback_query.message.edit_text(text=usings.send_ques_text, reply_markup=usings.cancel_markup)
    # set state to receive qustion
    await state.set_state(bot_states.question)
    # saving message id to remove cancel button in future
    await state.update_data(message = callback_query.message.message_id)

# processing pseudonimous question
@dp.message(bot_states.question)
async def ques_handle_process(message: types.Message, state: FSMContext):
    # check only text or media with caption
    if message.text or message.caption:
        if message.photo or message.video or message.audio or message.document or message.voice:
            # send question to admin and media in another message
            sended_message = await bot.send_message(chat_id=admin_id, text=f"Был получен вопрос от @{message.from_user.username}:\n{message.caption}\nПрикреплённое вложение:")
            await message.copy_to(chat_id=admin_id, caption=" ")
        else:
            # send question to admin with only text
            sended_message = await bot.send_message(chat_id=admin_id, text=f"Был получен вопрос от @{message.from_user.username}:\n{message.text}")
        # write to database information about sender
        await write_question_data(sended_message.message_id, message.chat.id, message.message_id)
        # send success message to sender
        await message.answer(text="✅ Ваша вопрос был отправлен успешно! Через некоторое время прийдет ответ.", reply_markup=usings.after_send(button_callback_data="ques_button"))
        # removing cancel button
        await usings.rem_cancel_button(message=message, state=state, text=usings.send_ques_text)
        # clearing state
        await state.set_state(None)
    else:
        # for any type of message except text or media with caption, such as stickers
        await message.reply(text="🚫 Допускается только текст или вложение с текстом!")

# send answer from admin
@dp.message((F.chat.id == int(admin_id)) & (F.reply_to_message))
async def ques_handle_answer(message: types.Message, state: FSMContext):
    # fetch information about where send answer
    data = await get_question_data(message.reply_to_message.message_id)
    # check if replied message id in database
    if data:
        # send answer to questioner
        sender_chat_id, sender_message_id = data
        await message.send_copy(chat_id=sender_chat_id, reply_to_message_id=sender_message_id)
        # send success message to admin
        await message.reply(text="✅ Ответ был отправлен успешно!")
    else:
        # if replied message id not in database
        await message.reply(text="🚫 Не удалось найти отправителя вопроса.")

# send pasta
@dp.callback_query(F.data == "pasta_button")
async def pasta_handle(callback_query: CallbackQuery, state: FSMContext):
    # answering callback query and edit message
    await callback_query.answer()
    await callback_query.message.edit_text(text=usings.send_pasta_text, reply_markup=usings.cancel_markup)
    # set state to receive pasta message
    await state.set_state(bot_states.pasta)
    # saving message id to remove cancel button in future
    await state.update_data(message = callback_query.message.message_id)

# processing pasta message
@dp.message(bot_states.pasta)
async def pasta_handle_process(message: types.Message, state: FSMContext):
    # only text check
    if message.text:
        # send pasta to admin
        await bot.send_message(chat_id=admin_id, text=f"Была получена паста от @{message.from_user.username}:\n{message.text}")
        # send success message to sender
        await message.answer(text="✅ Ваша паста была отправлена успешно!", reply_markup=usings.after_send(button_callback_data="pasta_button"))
        # removing cancel button
        await usings.rem_cancel_button(message=message, state=state, text=usings.send_pasta_text)
        # clearing state
        await state.set_state(None)
    else:
        # for any type of message, except text
        await message.reply(text="🚫 Допускается только текст!")

# bot strating
async def main():
    logging.basicConfig(level=logging.INFO)
    await setup_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())