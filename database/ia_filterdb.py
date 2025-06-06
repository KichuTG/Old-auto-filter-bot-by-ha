import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError, OperationFailure 
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import USE_CAPTION_FILTER, FILES_DATABASE_URL, SECOND_FILES_DATABASE_URL, DATABASE_NAME, COLLECTION_NAME, MAX_BTN

logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(FILES_DATABASE_URL)
db = client[DATABASE_NAME]
instance = Instance.from_db(db)

@instance.register
class Media(Document):
    file_id = fields.StrField(attribute='_id')
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    caption = fields.StrField(allow_none=True)

    class Meta:
        indexes = ('$file_name', )
        collection_name = COLLECTION_NAME
        strict = False



#second db
if SECOND_FILES_DATABASE_URL:
    second_client = AsyncIOMotorClient(SECOND_FILES_DATABASE_URL)
    second_db = second_client[DATABASE_NAME]
    second_instance = Instance.from_db(second_db)

    @second_instance.register
    class SecondMedia(Document):

        file_id = fields.StrField(attribute='_id')
        file_name = fields.StrField(required=True)
        file_size = fields.IntField(required=True)
        caption = fields.StrField(allow_none=True)

        class Meta:
             indexes = ('$file_name', )
             collection_name = COLLECTION_NAME
             strict = False




async def save_file(media):
    """Save file in database"""

    # TODO: Find better way to get same file_id for same media to avoid duplicates
    file_id = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"@\w+|(_|\-|\.|\+)", " ", str(media.file_name))
    file_caption = re.sub(r"@\w+|(_|\-|\.|\+)", " ", str(media.caption))
    try:
        file = Media(
            file_id=file_id,
            file_name=file_name,
            file_size=media.file_size,
            caption=file_caption
        )
    except ValidationError:
        logger.error(f'Saving Error - {file_name}')
        return 'err'
    else:
        try:
            await file.commit()
        except DuplicateKeyError:      
            logger.warning(f'Already Saved - {file_name}')
            return 'dup'
        except OperationFailure: #if 1st db is full
            if SECOND_FILES_DATABASE_URL:
                file = SecondMedia(
                    file_id=file_id,
                    file_name=file_name,
                    file_size=media.file_size,
                    caption=file_caption
                    )
                try:
                    await file.commit()
                    logger.info(f'Saved to 2nd db - {file_name}')
                    return 'suc'
                except DuplicateKeyError:
                    logger.warning(f'Already Saved in 2nd db - {file_name}')
                    return 'dup'
        else:
            logger.info(f'Saved - {file_name}')
            return 'suc'

async def get_search_results(query, max_results=MAX_BTN, offset=0, lang=None):
    query = str(query) # to ensure the query is string to stripe.
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]') 
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        regex = query

    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}

    cursor = Media.find(filter)
    results = [doc async for doc in cursor]

    if SECOND_FILES_DATABASE_URL:
        cursor2 = SecondMedia.find(filter)
        results.extend([doc async for doc in cursor2])



    if lang:
        lang_files = [file for file in results if lang in file.file_name.lower()]
        files = lang_files[offset:][:max_results]
        total_results = len(lang_files)
        next_offset = offset + max_results
        if next_offset >= total_results:
            next_offset = ''
        return files, next_offset, total_results
        

    total_results = len(results)
    files = results[offset:][:max_results]
    next_offset = offset + max_results
    if next_offset >= total_results:
        next_offset = ''   
    return files, next_offset, total_results
    
    
async def delete_files(query):
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        regex = query
    filter = {'file_name': regex}
    cursor = Media.find(filter)
    results = [doc async for doc in cursor]
    if SECOND_FILES_DATABASE_URL:
        cursor2 = SecondMedia.find(filter)
        results.extend([doc async for doc in cursor2])
    total = len(results)
    return total, results

async def get_file_details(query):
    filter = {'file_id': query}
    cursor = Media.find(filter)
    filedetails = await cursor.to_list(length=1)
    if not filedetails:
        cursor2 = SecondMedia.find(filter)
        filedetails = await cursor2.to_list(length=1)
        return filedetails
    return filedetails

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0

            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    return file_id
