import logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logging.getLogger('pyrogram').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

import os
import time
import asyncio
#import uvloop
from pyrogram import types
from pyrogram import Client
from pyrogram.errors import FloodWait
from aiohttp import web
from typing import Union, Optional, AsyncGenerator
from web import web_app
from info import LOG_CHANNEL, API_ID, DATA_DATABASE_URL, API_HASH, BOT_TOKEN, PORT, BIN_CHANNEL, ADMINS, SECOND_FILES_DATABASE_URL, FILES_DATABASE_URL
from utils import temp, get_readable_time
from database.users_chats_db import db
from database.ia_filterdb import Media
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

#uvloop.install()

class Bot(Client):
    def __init__(self):
        super().__init__(
            name='Auto_Filter_Bot',
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"}
        )

    async def start(self):
        try:
            await super().start()
        except FloodWait as e:
            time_ = get_readable_time(e.value)
            logger.warning(f"Flood Wait Occured, Wait For: {time_}")
            asyncio.sleep(e.value)
            logger.info("Now Ready For Deploying !")
        temp.START_TIME = time.time()
        data_db = MongoClient(DATA_DATABASE_URL, server_api=ServerApi('1'))
        try:
            data_db.admin.command('ping')
            logger.info("Successfully connected to DATA_DATABASE_URL")
        except Exception as e:
            logger.error("Make sure DATA_DATABASE_URL is correct, exiting now")
            exit()
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        files_db = MongoClient(FILES_DATABASE_URL, server_api=ServerApi('1'))
        try:
            files_db.admin.command('ping')
            logger.info("Successfully connected to FILES_DATABASE_URL")
        except Exception as e:
            logger.error("Make sure FILES_DATABASE_URL is correct, exiting now")
            exit()
        if SECOND_FILES_DATABASE_URL:
            secnd_files_db = MongoClient(SECOND_FILES_DATABASE_URL, server_api=ServerApi('1'))
            try:
                secnd_files_db.admin.command('ping')
                logger.info("Successfully connected to SECOND_FILES_DATABASE_URL")
            except:
                logger.error("Make sure SECOND_FILES_DATABASE_URL is correct, exiting now")
                exit()

        if os.path.exists('restart.txt'):
            with open("restart.txt") as file:
                chat_id, msg_id = map(int, file)
            try:
                await self.edit_message_text(chat_id=chat_id, message_id=msg_id, text='Restarted Successfully!')
            except:
                pass
            os.remove('restart.txt')
        temp.BOT = self
        await Media.ensure_indexes()
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        username = '@' + me.username
        logger.info(f"{me.first_name} is started now 🤗 (DC ID - {me.dc_id})")
        app = web.AppRunner(web_app)
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()
        try:
            await self.send_message(chat_id=LOG_CHANNEL, text=f"<b>{me.mention} Restarted! 🤖</b>")
        except:
            logger.error("Make sure bot admin in LOG_CHANNEL, exiting now")
            exit()
        try:
            m = await self.send_message(chat_id=BIN_CHANNEL, text="Test")
            await m.delete()
        except:
            logger.error("Make sure bot admin in BIN_CHANNEL, exiting now")
            exit()
        for admin in ADMINS:
            try:
                await self.send_message(chat_id=admin, text="<b>✅ ʙᴏᴛ ʀᴇsᴛᴀʀᴛᴇᴅ</b>")
            except:
                logger.warning(f"Admin ({admin}) not started this bot yet")

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot Stopped! Bye...")

    async def iter_messages(self: Client, chat_id: Union[int, str], limit: int, offset: int = 0) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially.
        This convenience method does the same as repeatedly calling :meth:`~hydrogram.Client.get_messages` in a loop, thus saving
        you from the hassle of setting up boilerplate code. It is useful for getting the whole chat messages with a
        single call.
        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).
                
            limit (``int``):
                Identifier of the last message to be returned.
                
            offset (``int``, *optional*):
                Identifier of the first message to be returned.
                Defaults to 0.
        Returns:
            ``Generator``: A generator yielding :obj:`~hydrogram.types.Message` objects.
        Example:
            .. code-block:: python
                async for message in app.iter_messages("HydrogramNews", 1000, 100):
                    print(message.text)
        """
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current+new_diff+1)))
            for message in messages:
                yield message
                current += 1

app = Bot()
app.run()
