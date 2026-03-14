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
    async_add_entities([SentryBoxPackageDetectedBinarySensor(coordinator, entry)])


class SentryBoxPackageDetectedBinarySensor(SentryBoxBinarySensorEntity):
    """Represent the package detection state."""

    _attr_name = "Package Detected"
    _attr_icon = "mdi:package-variant-closed-check"

    def __init__(self, coordinator: SentryBoxCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, "package_detected")

    @property
    def is_on(self) -> bool | None:
        """Return whether a package is currently detected."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.package_detected
