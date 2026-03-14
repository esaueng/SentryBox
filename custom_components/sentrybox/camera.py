"""Camera platform for SentryBox."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SentryBoxCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SentryBox camera entity."""
    coordinator: SentryBoxCoordinator = entry.runtime_data
    async_add_entities([SentryBoxLastAnalysisCamera(coordinator, entry)])


class SentryBoxLastAnalysisCamera(CoordinatorEntity[SentryBoxCoordinator], Camera):
    """Expose the latest frame sent to the LLM as a camera entity."""

    _attr_has_entity_name = True
    _attr_name = "Last Analysis Frame"
    _attr_icon = "mdi:cctv"
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: SentryBoxCoordinator, entry: ConfigEntry) -> None:
        """Initialize the camera entity."""
        Camera.__init__(self)
        CoordinatorEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_analysis_frame"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or entry.data.get("name", "SentryBox"),
            "manufacturer": "SentryBox",
            "model": coordinator.model_name,
            "configuration_url": coordinator.ollama_base_url,
        }

    @property
    def available(self) -> bool:
        """Return whether a preview frame is available."""
        return self.coordinator.last_preview_bytes is not None

    @property
    def is_recording(self) -> bool:
        """Return False because this is a snapshot camera."""
        return False

    @property
    def is_streaming(self) -> bool:
        """Return False because this entity serves the latest still frame."""
        return False

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return the latest analyzed image bytes."""
        del width, height
        return self.coordinator.last_preview_bytes
