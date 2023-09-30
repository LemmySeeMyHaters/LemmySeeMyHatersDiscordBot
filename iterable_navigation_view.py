from __future__ import annotations

import contextlib
import datetime
from typing import Sequence, Optional, Any, MutableMapping

import hikari
from miru import View, Context, ViewContext
from miru.ext.nav import IndicatorButton, NavButton, NextButton, PrevButton, NavItem, StopButton

from lemmy_see_my_haters_iterator import LemmySeeMyHatersIterator


class MyPrevButton(PrevButton):
    async def callback(self, context: ViewContext) -> None:
        self.view.current_page -= 1
        await self.view.send_cached_page(context)


class MyNextButton(NextButton):
    async def callback(self, context: ViewContext) -> None:
        self.view.current_page += 1
        if len(self.view._cached_pages) > self.view.current_page:
            await self.view.send_cached_page(context)
        else:
            await self.view.send_page(context)


class IteratorNavigationView(View):
    def __init__(
        self,
        *,
        pages: LemmySeeMyHatersIterator,
        buttons: Optional[Sequence[NavButton]] = None,
        timeout: Optional[float | int | datetime.timedelta] = 120.0,
        autodefer: bool = True,
    ) -> None:
        self._pages: LemmySeeMyHatersIterator = pages
        self._cached_pages: list[list[hikari.Embed]] = []
        self._current_page: int = 0
        self._ephemeral: bool = False
        # If the nav is using interaction-based handling or not
        self._using_inter: bool = False
        # The last interaction received, used for inter-based handling
        self._inter: Optional[hikari.MessageResponseMixin[Any]] = None
        super().__init__(timeout=timeout, autodefer=autodefer)

        if buttons is not None:
            for button in buttons:
                self.add_item(button)
        else:
            default_buttons = [MyPrevButton(), IndicatorButton(disabled=True), MyNextButton(), StopButton()]
            for default_button in default_buttons:
                self.add_item(default_button)

    @property
    def pages(self) -> LemmySeeMyHatersIterator:
        """
        The pages the navigator is iterating through.
        """
        return self._pages

    @property
    def current_page(self) -> int:
        """
        The current page of the navigator, zero-indexed integer.
        """
        return self._current_page

    @current_page.setter
    def current_page(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError("Expected type int for property current_page.")

        # Ensure this value is always correct
        self._current_page = max(0, min(value, len(self.pages) - 1))

    @property
    def ephemeral(self) -> bool:
        """
        Value determining if the navigator is sent ephemerally or not.
        This value will be ignored if the navigator is not sent on an interaction.
        """
        return self._ephemeral

    async def _get_page_payload(self, pages: LemmySeeMyHatersIterator) -> MutableMapping[str, Any]:
        """Get the page content that is to be sent."""

        try:
            vote = await anext(pages)
        except StopAsyncIteration:
            vote = hikari.Embed(title=pages.params["url"], description="Nothing to see here.")

        embeds = [vote] if isinstance(vote, hikari.Embed) else []
        self._cached_pages.append(embeds)

        if not embeds:
            raise TypeError(f"Expected type 'str' or 'hikari.Embed' to send as page, not '{vote.__class__.__name__}'.")

        if self.ephemeral:
            return dict(
                content="",
                embeds=embeds,
                components=self,
                flags=hikari.MessageFlag.EPHEMERAL,
            )
        else:
            return dict(content="", embeds=embeds, components=self)

    async def send_cached_page(self, context: Context[Any]) -> None:
        await self._update_buttons()

        embeds = self._cached_pages[self.current_page]
        if self.ephemeral:
            payload_dict = dict(
                content="",
                embeds=embeds,
                components=self,
                flags=hikari.MessageFlag.EPHEMERAL,
            )
        else:
            payload_dict = dict(content="", embeds=embeds, components=self)
        await context.edit_response(**payload_dict, attachment=None)

    async def send_page(self, context: Context[Any], page_index: Optional[int] = None) -> None:
        """Send a page, editing the original message.

        Parameters
        ----------
        context : Context
            The context object that should be used to send this page
        page_index : Optional[int], optional
            The index of the page to send, if not specifed, sends the current page, by default None
        """
        if page_index is not None:
            self.current_page = page_index

        await self._update_buttons()

        payload = await self._get_page_payload(self.pages)

        self._inter = context.interaction  # Update latest inter

        await context.edit_response(**payload, attachment=None)

    async def _update_buttons(self) -> None:
        for button in self.children:
            if isinstance(button, NavItem):
                await button.before_page_change()

    async def send(
        self,
        to: hikari.SnowflakeishOr[hikari.TextableChannel] | hikari.MessageResponseMixin[Any],
        *,
        start_at: int = 0,
        ephemeral: bool = False,
        responded: bool = False,
    ) -> None:
        """Start up the navigator, send the first page, and start listening for interactions.

        Parameters
        ----------
        to : Union[hikari.SnowflakeishOr[hikari.PartialChannel], hikari.MessageResponseMixin[Any]]
            The channel or interaction to send the navigator to.
        start_at : int
            If provided, the page number to start the pagination at.
        ephemeral : bool
            If an interaction was provided, determines if the navigator will be sent ephemerally or not.
        responded : bool
            If an interaction was provided, determines if the interaction was previously acknowledged or not.
        """
        self._ephemeral = ephemeral if isinstance(to, hikari.MessageResponseMixin) else False
        self._using_inter = isinstance(to, hikari.MessageResponseMixin)

        payload = await self._get_page_payload(self.pages)
        await self._update_buttons()

        if self.ephemeral and self.timeout and self.timeout > 900:
            print(
                f"Using a timeout value longer than 900 seconds (Used {self.timeout}) in ephemeral navigator {type(self).__name__} may cause on_timeout to fail."
            )

        if isinstance(to, (int, hikari.TextableChannel)):
            channel = hikari.Snowflake(to)
            message = await self.app.rest.create_message(channel, **payload)

        else:
            self._inter = to
            if not responded:
                await to.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE,
                    **payload,
                )
                message = await to.fetch_initial_response()
            else:
                message = await to.execute(**payload)

        if self.is_persistent and not self.is_bound:
            return  # Do not start the view if unbound persistent

        await self.start(message)
