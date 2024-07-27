import discord


def build_bookmark_embed(message: discord.Message, title: str):
    embed = discord.Embed(title = title, description=message.content, colour=0x68C290)
    embed.set_author(
        name=message.author,
        icon_url=message.author.display_avatar.url
    )
    return embed
