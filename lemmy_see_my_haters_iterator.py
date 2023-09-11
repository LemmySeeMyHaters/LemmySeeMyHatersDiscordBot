import math
from abc import ABC
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional, TypedDict

import aiohttp
import hikari


@dataclass(frozen=True)
class LemmyVote:
    name: str
    score: int
    actor_id: str
    created_utc: float

    def __str__(self) -> str:
        return f"- [<t:{int(self.created_utc)}>] [{self.name}]({self.actor_id}): **{self.score}**"


@dataclass(frozen=True)
class VotesResponse:
    votes: list[LemmyVote]
    total_count: int
    next_offset: Optional[int]
    total_score: int
    upvotes: int
    downvotes: int


class IteratorParams(TypedDict):
    url: str
    limit: int
    offset: int
    username: Optional[str]
    votes_filter: str


async def fetch_next_data(url: str, query: IteratorParams) -> VotesResponse:
    tmp_query = {"url": query["url"], "limit": query["limit"], "offset": query["offset"], "votes_filter": query["votes_filter"]}
    if query["username"] is not None:
        tmp_query["username"] = query["username"]

    async with (aiohttp.ClientSession() as session):
        async with session.get(url, params=tmp_query) as resp:
            response = await resp.json()
            return VotesResponse(
                votes=[LemmyVote(**x) for x in response["votes"]],
                next_offset=response["next_offset"],
                total_count=response["total_count"],
                total_score=response["total_score"],
                upvotes=response["upvotes"],
                downvotes=response["downvotes"],
            )


class LemmySeeMyHatersIterator(AsyncIterator[hikari.Embed], ABC):
    """
    Iterator class for fetching Lemmy votes with optional filtering by username and votes filter.

    :param str api_base_path: The base API path for Lemmy.
    :param str url: The URL of the post or comment for which to fetch votes.
    :param int limit: The maximum number of votes to fetch in each batch.
    :param int offset: The offset from which to start fetching votes.
    :param str username: The username for filtering votes by a specific user (default: None).
    :param str votes_filter: A string specifying the type of votes to fetch (e.g., 'Upvoted', 'Downvoted', 'All').

    :ivar str api_base_path: The base API path for Lemmy.
    :ivar dict[str, str | int] params: A dictionary of query parameters for the API request.
    :ivar VotesResponse _current_batch: The current batch of votes fetched.
    :ivar int _batch_idx: The index of the vote within the current batch.
    :ivar bool _has_next: Indicates whether there are more votes to fetch.

    """

    def __init__(self, api_base_path: str, url: str, limit: int, offset: int, username: Optional[str], votes_filter: str):
        super().__init__()
        self.api_base_path: str = api_base_path
        self.params: IteratorParams = {"url": url, "limit": limit, "offset": offset, "username": username, "votes_filter": votes_filter}
        self._current_batch: VotesResponse = VotesResponse(votes=[], next_offset=0, total_count=0, total_score=0, upvotes=0, downvotes=0)
        self._has_next: bool = True

    def __aiter__(self) -> AsyncIterator[hikari.Embed]:
        """
        Returns the iterator object.
        """
        return self

    async def __anext__(self) -> hikari.Embed:
        """
        Asynchronously fetches the next Lemmy vote.

        :raises StopAsyncIteration: When there are no more votes to fetch.
        :returns: The next LemmyVote object.
        """
        if not self._has_next:
            raise StopAsyncIteration

        self._current_batch = await fetch_next_data(self.api_base_path, self.params)
        if self._current_batch.next_offset is not None:
            self._has_next = True
            self.params["offset"] = self._current_batch.next_offset
        else:
            self._has_next = False

        # If we don't get any votes on first request
        vote_list = "\n".join(str(vote) for vote in self._current_batch.votes)
        desc = f"""**Votes Summary**:
        
        **Upvotes**: {self._current_batch.upvotes}
        **Downvotes**: {self._current_batch.downvotes}
        **Upvote/Downvote Ratio**: {self._current_batch.upvotes / self._current_batch.total_count:.3f}
        
        {vote_list}
        """
        if vote_list:
            return hikari.Embed(title=self.params["url"], description=desc)
        else:
            raise StopAsyncIteration

    def __len__(self) -> int:
        """
        Returns the total count of votes for the specified URL and filters.

        :returns: The total count of votes.
        """
        return math.ceil(self._current_batch.total_count / self.params["limit"])
