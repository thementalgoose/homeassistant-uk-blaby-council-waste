"""Config flow for Blaby waste."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, TextSelector

from .api import AddressOption, BlabyWasteClient, BlabyWasteCommunicationError, normalize_postcode
from .const import (
    CONF_ADDRESS,
    CONF_LOCATION_REF,
    CONF_POSTCODE,
    CONF_SCAN_INTERVAL_HOURS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
)


class BlabyWasteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Blaby waste."""

    VERSION = 1

    def __init__(self) -> None:
        self._postcode: str | None = None
        self._addresses: list[AddressOption] = []

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._postcode = normalize_postcode(user_input[CONF_POSTCODE])
            client = BlabyWasteClient(async_get_clientsession(self.hass))

            try:
                self._addresses = await client.lookup_addresses(self._postcode)
            except BlabyWasteCommunicationError:
                errors["base"] = "cannot_connect"
            else:
                if not self._addresses:
                    errors["base"] = "no_addresses"
                else:
                    return await self.async_step_address()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_POSTCODE): TextSelector()}),
            errors=errors,
        )

    async def async_step_address(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Select an address for the postcode."""
        if self._postcode is None or not self._addresses:
            return await self.async_step_user()

        if user_input is not None:
            location_ref = user_input[CONF_LOCATION_REF]
            selected = next(
                option for option in self._addresses if option.location_ref == location_ref
            )

            await self.async_set_unique_id(location_ref)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=selected.label,
                data={
                    CONF_POSTCODE: self._postcode,
                    CONF_LOCATION_REF: selected.location_ref,
                    CONF_ADDRESS: selected.label,
                },
            )

        return self.async_show_form(
            step_id="address",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_REF): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": option.location_ref, "label": option.label}
                                for option in self._addresses
                            ]
                        )
                    )
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return BlabyWasteOptionsFlow(config_entry)


class BlabyWasteOptionsFlow(config_entries.OptionsFlow):
    """Options flow to re-select the address."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._postcode = config_entry.data[CONF_POSTCODE]
        self._addresses: list[AddressOption] = []
        self._scan_interval_hours = config_entry.options.get(
            CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS
        )

    async def async_step_init(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Allow the postcode or update interval to be changed."""
        errors: dict[str, str] = {}

        if user_input is not None:
            new_postcode = normalize_postcode(user_input[CONF_POSTCODE])
            self._scan_interval_hours = int(user_input[CONF_SCAN_INTERVAL_HOURS])

            if new_postcode == self._config_entry.data[CONF_POSTCODE]:
                return await self._update_entry_options()

            self._postcode = new_postcode
            client = BlabyWasteClient(async_get_clientsession(self.hass))

            try:
                self._addresses = await client.lookup_addresses(self._postcode)
            except BlabyWasteCommunicationError:
                errors["base"] = "cannot_connect"
            else:
                if not self._addresses:
                    errors["base"] = "no_addresses"
                else:
                    return await self.async_step_address()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POSTCODE, default=self._postcode): TextSelector(),
                    vol.Required(
                        CONF_SCAN_INTERVAL_HOURS,
                        default=self._scan_interval_hours,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
                }
            ),
            errors=errors,
        )

    async def async_step_address(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to pick a new address."""
        if user_input is not None:
            location_ref = user_input[CONF_LOCATION_REF]
            selected = next(
                option for option in self._addresses if option.location_ref == location_ref
            )

            self.hass.config_entries.async_update_entry(
                self._config_entry,
                title=selected.label,
                data={
                    CONF_POSTCODE: self._postcode,
                    CONF_LOCATION_REF: selected.location_ref,
                    CONF_ADDRESS: selected.label,
                },
            )
            return await self._update_entry_options(reload_entry=True)

        return self.async_show_form(
            step_id="address",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_REF): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": option.location_ref, "label": option.label}
                                for option in self._addresses
                            ]
                        )
                    )
                }
            ),
        )

    async def _update_entry_options(self, reload_entry: bool = True) -> FlowResult:
        """Persist the polling interval and optionally reload the entry."""
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            options={CONF_SCAN_INTERVAL_HOURS: self._scan_interval_hours},
        )
        if reload_entry:
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
        return self.async_create_entry(title="", data={})
