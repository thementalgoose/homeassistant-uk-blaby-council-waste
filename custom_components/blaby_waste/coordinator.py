"""Coordinator for Blaby waste data."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BlabyWasteClient, BlabyWasteCommunicationError, BlabyWasteError
from .const import (
    CONF_LOCATION_REF,
    CONF_SCAN_INTERVAL_HOURS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    NAME,
)

LOGGER = logging.getLogger(__name__)


class BlabyWasteDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinate Blaby waste data updates."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: BlabyWasteClient,
    ) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=NAME,
            update_interval=self._get_update_interval(entry),
        )
        self.config_entry = entry
        self._client = client

    @staticmethod
    def _get_update_interval(entry: ConfigEntry):
        """Return the configured polling interval."""
        from datetime import timedelta

        hours = entry.options.get(
            CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS
        )
        return timedelta(hours=hours)

    async def _async_update_data(self):
        """Fetch the latest collection data."""
        try:
            return await self._client.fetch_collections(
                self.config_entry.data[CONF_LOCATION_REF]
            )
        except BlabyWasteCommunicationError as err:
            raise UpdateFailed(f"Unable to communicate with Blaby: {err}") from err
        except BlabyWasteError as err:
            raise UpdateFailed(f"Unable to parse Blaby collections: {err}") from err
