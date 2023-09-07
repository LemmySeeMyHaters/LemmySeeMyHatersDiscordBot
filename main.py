#!venv/bin/python
import json
from math import ceil
from os import getenv
from typing import Annotated
from typing import Any, Optional, cast

import crescent
import hikari
import miru
from dotenv import load_dotenv
from miru.ext import nav
from miru.ext.nav import NavItem

from lemmy_api import fetch_comment_votes, fetch_post_votes, json_to_markdown, VotesResponse

load_dotenv()
bot = hikari.GatewayBot(getenv("DISCORD_TOKEN", ""))
miru.install(bot)
client = crescent.Client(bot)

choices = (
    hikari.CommandChoice(name="All", value="All"),
    hikari.CommandChoice(name="Upvotes Only", value="Upvotes"),
    hikari.CommandChoice(name="Downvotes Only", value="Downvotes"),
)


class MyNavigationView(nav.NavigatorView):
    async def send_page(self, context: miru.Context[Any], page_index: Optional[int] = None) -> None:
        if page_index is not None:
            self.current_page = page_index

        page = self.pages[self.current_page]
        if isinstance(page, str):
            page = self.pages[self.current_page]
            slash_cmd_args = json.loads(cast(str, page))
            response_data = await fetch_comment_votes(
                slash_cmd_args["url"],
                slash_cmd_args["limit"],
                slash_cmd_args["limit"] * self.current_page,
                slash_cmd_args["username"],
                slash_cmd_args["votes_filter"],
            )
            page = json_to_markdown(response_data)

        for button in self.children:
            if isinstance(button, NavItem):
                await button.before_page_change()

        payload = self._get_page_payload(page)

        self._inter = context.interaction

        await context.edit_response(**payload, attachment=None)


async def navigation_view_creator(response_data: VotesResponse, url: str, limit: int, username: Optional[str], votes_filter: str) -> MyNavigationView:
    total_pages = ceil(response_data["total_count"] / limit)
    slash_cmds_args: str = json.dumps({"url": url, "limit": limit, "username": username, "votes_filter": votes_filter})
    pages: list[str | hikari.Embed] = [json_to_markdown(response_data), *([slash_cmds_args] * (total_pages - 1))]
    buttons = [nav.PrevButton(), nav.StopButton(), nav.NextButton(), nav.IndicatorButton(disabled=True)]
    navigator = MyNavigationView(pages=pages, buttons=buttons, timeout=30)
    return navigator


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
    response_data = await fetch_post_votes(url, limit, 0, username, votes_filter)
    navigator = await navigation_view_creator(response_data, url, limit, username, votes_filter)
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
    response_data = await fetch_comment_votes(url, limit, 0, username, votes_filter)
    navigator = await navigation_view_creator(response_data, url, limit, username, votes_filter)
    await navigator.send(ctx.channel_id)


def main() -> None:
    bot.run()


if __name__ == "__main__":
    main()
