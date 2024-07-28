from demobot_config import db

import discobase


@db.table
class BookmarkedMessage(discobase.Table):
    user_id: int
    title: str
    author_name: str
    author_avatar_url: str
    message_content: str
