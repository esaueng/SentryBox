"""Image platform for SentryBox."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SentryBoxCoordinator
from .entity import SentryBoxEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SentryBox image entity."""
    coordinator: SentryBoxCoordinator = entry.runtime_data
    async_add_entities([SentryBoxLastAnalysisImage(coordinator, entry)])


class SentryBoxLastAnalysisImage(SentryBoxEntity, ImageEntity):
    """Render the last analyzed frame sent to Ollama."""

    _attr_name = "Last Analysis Frame"
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: SentryBoxCoordinator, entry: ConfigEntry) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, entry, "last_analysis_frame")

    @property
    def image_last_updated(self) -> datetime | None:
        """Return the timestamp of the latest preview update."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.last_analyzed

    async def async_image(self) -> bytes | None:
        """Return the latest analyzed image bytes."""
        if self.coordinator.data is None or self.coordinator.data.preview_image_path is None:
            return None
        return await self.hass.async_add_executor_job(
            self._read_image_bytes,
            self.coordinator.data.preview_image_path,
        )

    @staticmethod
    def _read_image_bytes(path: str) -> bytes | None:
        """Read image bytes from disk."""
        try:
            with open(path, "rb") as image_file:
                return image_file.read()
        except FileNotFoundError:
            return None
