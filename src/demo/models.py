from config import db

import discobase


@db.table
class BookmarkedMessage(discobase.Table):
    user_id: int
    title: str
    content: str
    author_id: int
    channel_id: int
    message_id: int
