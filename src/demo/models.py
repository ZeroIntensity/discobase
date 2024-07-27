from demobot_config import db

import discobase


@db.table
class BookmarkedMessage(discobase.Table):
    user_id: int
    title: str
    channel_id: int
    message_id: int
