import discobase

db = discobase.Database("personal_discobase_server")

@db.table
class BookmarkedMessage(discobase.Table):
    user_id: int
    message_id: int
