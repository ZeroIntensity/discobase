import discord
import typing
import enum

class Result(enum.StrEnum):
    SUCCESS = "s"
    FAILURE = "f"
    PARTIAL = "p"
    ERROR = "e"

class BookmarkStorage:
    def __init__(self):
        self.bookmarks = {}
    
    def bmc(self, user: discord.User, command: str, args: dict, global_ = False, /):
        """Host function to call commands.

        Args:
            user (discord.User): Required. Who is calling the command.
            command (str): _description_
            args (list): _description_
        """

    def _add(self, user: discord.User, mid: discord.Message.id, content: discord.Message.content) -> tuple[Result,]:
        """Add a message to the bookmarks.

        Args:
            user (discord.User): _description_
            mid (discord.Message.id): _description_
            content (discord.Message.content): _description_

        Returns:
            tuple[Result]: _description_
        """
   

    def _get(self, user: discord.User | typing.Literal["global"], searchstring: str) -> tuple[Result, list[discord.Message]]:
        """Get bookmarks for a user, or across the whole server. If getting bookmarks for the whole sever, a search string is required.

        Args:
            user (discord.User | typing.Literal["global"]): The user to get bookmarks for, or "global" to get bookmarks for the whole server.
            mid (discord.Message.id): The message ID of the bookmarked message.
            content (discord.Message.content): The content of the bookmarked message.

        Returns:
            tuple[Result, list[discord.Message]]: The Result (see Result Enum), and the list of returned bookmarks
        """
    def _remove(self, user: discord.User, mid: discord.Message.id) -> tuple[Result]:
        """Remove a bookmark from the list.

        Args:
            user (discord.User): The user to remove the bookmark from.
            mid (discord.Message.id): The message ID of the bookmarked message. The owner of the message must be the user passed in.
        
        Returns:
            tuple[Result]: The Result (see Result Enum). Will return FAILURE if the user is not the owner of the message.
        """

    def _clear(self, user: discord.User) -> tuple[Result]:
        """Clear all bookmarks for a user.

        Args:
            user (discord.User): The user to clear bookmarks for.

        Returns:
            tuple[Result]: The Result (see Result Enum).
        """

    def _clear_all(self) -> tuple[Result]:
        """Clear all bookmarks for the server.

        This function should only be available to privaledged users. 
        
        Returns:
            tuple[Result]: The Result (see Result Enum).
        """
        
    def db_sync(self) -> None:
        """Sync the stored bookmarks with the database.
        
        Should be called after every few changes to the bookmarks.
        
        """