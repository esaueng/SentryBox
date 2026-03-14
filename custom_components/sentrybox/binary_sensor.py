"""Binary sensor platform for SentryBox."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SentryBoxCoordinator
from .entity import SentryBoxBinarySensorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SentryBox binary sensor."""
    coordinator: SentryBoxCoordinator = entry.runtime_data
    async_add_entities([SentryBoxDetectedBinarySensor(coordinator, entry)])


class SentryBoxDetectedBinarySensor(SentryBoxBinarySensorEntity):
    """Represent the configured detection state."""

    def __init__(self, coordinator: SentryBoxCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, "detected")

    @property
    def name(self) -> str | None:
        """Return the profile-aware entity name."""
        return self.coordinator.binary_sensor_name

    @property
    def icon(self) -> str | None:
        """Return the profile-aware icon."""
        return self.coordinator.binary_sensor_icon

    @property
    def is_on(self) -> bool | None:
        """Return whether the configured event is currently detected."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.detected
