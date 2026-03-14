"""Sensor platform for SentryBox."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SentryBoxCoordinator
from .entity import SentryBoxSensorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SentryBox sensors."""
    coordinator: SentryBoxCoordinator = entry.runtime_data
    async_add_entities(
        [
            SentryBoxConfidenceSensor(coordinator, entry),
            SentryBoxSummarySensor(coordinator, entry),
        ]
    )


class SentryBoxConfidenceSensor(SentryBoxSensorEntity):
    """Represent the current model confidence."""

    _attr_name = "Confidence"
    _attr_icon = "mdi:gauge"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: SentryBoxCoordinator, entry: ConfigEntry) -> None:
        """Initialize the confidence sensor."""
        super().__init__(coordinator, entry, "confidence")

    @property
    def native_value(self) -> float | None:
        """Return the current confidence value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.confidence


class SentryBoxSummarySensor(SentryBoxSensorEntity):
    """Represent the current model summary."""

    _attr_name = "Summary"
    _attr_icon = "mdi:text-box-search-outline"

    def __init__(self, coordinator: SentryBoxCoordinator, entry: ConfigEntry) -> None:
        """Initialize the summary sensor."""
        super().__init__(coordinator, entry, "summary")

    @property
    def native_value(self) -> str | None:
        """Return the summary from the most recent analysis."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.summary
