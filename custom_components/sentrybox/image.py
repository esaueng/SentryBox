"""Image platform for SentryBox."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
        self._preview_path = coordinator.preview_image_path
        self._image_last_updated = self._read_file_timestamp(self._preview_path)

        if coordinator.data is not None and coordinator.data.preview_image_path is not None:
            self._preview_path = coordinator.data.preview_image_path
            self._image_last_updated = coordinator.data.last_analyzed

    @property
    def available(self) -> bool:
        """Return whether a preview image is available."""
        return Path(self._preview_path).exists()

    @property
    def image_last_updated(self) -> datetime | None:
        """Return the timestamp of the latest preview update."""
        return self._image_last_updated

    async def async_image(self) -> bytes | None:
        """Return the latest analyzed image bytes."""
        if not Path(self._preview_path).exists():
            return None
        return await self.hass.async_add_executor_job(
            self._read_image_bytes,
            self._preview_path,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the cached preview path and timestamp from coordinator data."""
        if self.coordinator.data is not None and self.coordinator.data.preview_image_path:
            self._preview_path = self.coordinator.data.preview_image_path
            self._image_last_updated = self.coordinator.data.last_analyzed
        elif self._image_last_updated is None:
            self._image_last_updated = self._read_file_timestamp(self._preview_path)

        super()._handle_coordinator_update()

    @staticmethod
    def _read_image_bytes(path: str) -> bytes | None:
        """Read image bytes from disk."""
        try:
            with open(path, "rb") as image_file:
                return image_file.read()
        except FileNotFoundError:
            return None

    @staticmethod
    def _read_file_timestamp(path: str) -> datetime | None:
        """Read the file modification time for an existing preview."""
        try:
            return datetime.fromtimestamp(Path(path).stat().st_mtime)
        except FileNotFoundError:
            return None
