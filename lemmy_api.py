from os import getenv
from typing import Optional, TypedDict

import aiohttp
import hikari


class LemmyVote(TypedDict):
    name: str
    score: int
    actor_id: str


class VotesResponse(TypedDict):
    votes: list[LemmyVote]
    total_count: int
    next_offset: Optional[int]


def json_to_markdown(votes_response: VotesResponse) -> hikari.Embed:
    """
    Convert a list of vote dictionaries into a Markdown formatted list as an hikari.Embed.

    :param votes_response: A list of dictionaries containing 'votes', 'total_count', and 'next_offset' keys.
    :type votes_response: VotesResponse

    :return: An hikari.Embed object containing the Markdown formatted list of votes.
    :rtype: hikari.Embed
    """

    votes_md_list = [f"- [{vote['name']}]({vote['actor_id']}): {vote['score']}" for vote in votes_response["votes"]]
    return hikari.Embed(title="LemmySeeMyHaters", description="\n".join(votes_md_list))


def prepare_query(url: str, limit: int, offset: int, username: Optional[str], votes_filter: str) -> dict[str, str | int]:
    query: dict[str, str | int] = {"url": url, "limit": limit, "offset": offset, "votes_filter": votes_filter}
    if username is not None:
        query["username"] = username
    return query


async def fetch_comment_votes(url: str, limit: int, offset: int, username: Optional[str], votes_filter: str) -> VotesResponse:
    query = prepare_query(url, limit, offset, username, votes_filter)
    async with (aiohttp.ClientSession() as session):
        async with session.get(f"{getenv('BACKEND_URL')}/votes/comment", params=query) as resp:
            response: VotesResponse = await resp.json()
            return response


async def fetch_post_votes(url: str, limit: int, offset: int, username: Optional[str], votes_filter: str) -> VotesResponse:
    query = prepare_query(url, limit, offset, username, votes_filter)
    async with (aiohttp.ClientSession() as session):
        async with session.get(f"{getenv('BACKEND_URL')}/votes/post", params=query) as resp:
            response: VotesResponse = await resp.json()
            return response
