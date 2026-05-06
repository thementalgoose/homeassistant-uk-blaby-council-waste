"""Sensors for Blaby waste collections."""

from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .api import Collection
from .const import (
    ATTR_ADDRESS,
    ATTR_COLLECTION_DAY,
    ATTR_DAYS_UNTIL,
    ATTR_DAYS_UNTIL_COUNT,
    ATTR_FOLLOWING_DATE,
    ATTR_NEXT_DATE,
    CONF_LOCATION_REF,
    DOMAIN,
)
from .coordinator import BlabyWasteDataUpdateCoordinator


ICON_MAP = {
    "refuse": "mdi:trash-can",
    "food waste": "mdi:food-apple",
    "recycling": "mdi:recycle",
    "garden": "mdi:leaf",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blaby waste sensors."""
    coordinator: BlabyWasteDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for collection_name in coordinator.data.collections:
        icon = ICON_MAP.get(collection_name.lower(), "mdi:trash-can-outline")
        sensors.append(
            BlabyWasteCollectionSensor(
                coordinator,
                entry,
                SensorEntityDescription(
                    key=slugify(collection_name),
                    name=collection_name,
                    device_class=SensorDeviceClass.DATE,
                    icon=icon,
                ),
                collection_name,
            )
        )

    async_add_entities(sensors)


class BlabyWasteCollectionSensor(
    CoordinatorEntity[BlabyWasteDataUpdateCoordinator], SensorEntity
):
    """Representation of a Blaby waste collection sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: BlabyWasteDataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
        collection_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._collection_name = collection_name
        self._attr_has_entity_name = True
        self._attr_name = description.name
        self._attr_unique_id = (
            f"{entry.data[CONF_LOCATION_REF]}_{description.key}"
        )
        self._attr_icon = description.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_LOCATION_REF])},
            manufacturer="Blaby District Council",
            model="Waste collections",
            name=entry.title,
        )

    @property
    def native_value(self) -> date | None:
        """Return the next collection date."""
        collection = self._collection
        return collection.next_date if collection else None

    @property
    def extra_state_attributes(self) -> dict[str, str | int] | None:
        """Return extra details about the collection."""
        collection = self._collection
        if collection is None:
            return None

        days_until = (collection.next_date - date.today()).days
        attributes: dict[str, str | int] = {
            ATTR_ADDRESS: self.coordinator.data.address,
            ATTR_COLLECTION_DAY: self.coordinator.data.collection_day,
            ATTR_NEXT_DATE: _format_display_date(collection.next_date),
            ATTR_DAYS_UNTIL: f"{days_until} days",
            ATTR_DAYS_UNTIL_COUNT: days_until,
        }
        if collection.following_date is not None:
            attributes[ATTR_FOLLOWING_DATE] = _format_display_date(
                collection.following_date
            )
        return attributes

    @property
    def _collection(self) -> Collection | None:
        """Return the collection data for this sensor."""
        return self.coordinator.data.collections.get(self._collection_name)


def _format_display_date(value: date) -> str:
    """Format a date as d MMM yyyy."""
    return f"{value.day} {value.strftime('%b %Y')}"
