#!venv/bin/python
from os import getenv
from typing import Annotated
from typing import Optional

import crescent
import hikari
import miru
from dotenv import load_dotenv

from lemmy_see_my_haters_iterator import LemmySeeMyHatersIterator
from iterable_navigation_view import IteratorNavigationView

load_dotenv()
bot = hikari.GatewayBot(getenv("DISCORD_TOKEN", ""))
miru.install(bot)
client = crescent.Client(bot)

choices = (
    hikari.CommandChoice(name="All", value="All"),
    hikari.CommandChoice(name="Upvotes Only", value="Upvotes"),
    hikari.CommandChoice(name="Downvotes Only", value="Downvotes"),
)


@client.include
@crescent.command(
    description="Get votes information on Lemmy Post.",
    guild=int(getenv("TEST_SERVER_GUILD_ID", "0")),
)
async def post_votes(
    ctx: crescent.Context,
    url: str,
    limit: int = 10,
    username: Optional[str] = None,
    votes_filter: Annotated[str, crescent.Choices(*choices)] = "All",
) -> None:
    post_iter = LemmySeeMyHatersIterator(f"{getenv('BACKEND_URL', '')}/votes/post", url, limit, 0, username, votes_filter)
    navigator = IteratorNavigationView(pages=post_iter)
    await navigator.send(ctx.channel_id)


@client.include
@crescent.command(
    description="Get votes information on Lemmy Comment.",
    guild=int(getenv("TEST_SERVER_GUILD_ID", "0")),
)
async def comment_votes(
    ctx: crescent.Context,
    url: str,
    limit: int = 20,
    username: Optional[str] = None,
    votes_filter: Annotated[str, crescent.Choices(*choices)] = "All",
) -> None:
    await ctx.defer()
    comment_iter = LemmySeeMyHatersIterator(f"{getenv('BACKEND_URL', '')}/votes/comment", url, limit, 0, username, votes_filter)
    navigator = IteratorNavigationView(pages=comment_iter)
    await navigator.send(ctx.channel_id)


def main() -> None:
    bot.run()


if __name__ == "__main__":
    main()
