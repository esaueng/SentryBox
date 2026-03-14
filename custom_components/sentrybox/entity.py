"""Shared entity helpers for SentryBox."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SentryBoxCoordinator


class SentryBoxEntity(CoordinatorEntity[SentryBoxCoordinator]):
    """Base entity for SentryBox entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SentryBoxCoordinator,
        entry: ConfigEntry,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{entity_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or entry.data.get(CONF_NAME, "SentryBox"),
            manufacturer="SentryBox",
            model=coordinator.model_name,
            configuration_url=coordinator.ollama_base_url,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return shared entity attributes."""
        if self.coordinator.data is None:
            return {}

        result = self.coordinator.data
        return {
            "last_analyzed": result.last_analyzed.isoformat(),
            "model_name": result.model_name,
            "last_raw_response": result.raw_response,
            "last_image_path": result.snapshot_path,
            "preview_image_path": result.preview_image_path,
            "raw_package_detected": result.raw_package_detected,
            "model_package_detected": result.model_package_detected,
            "confidence_threshold": result.confidence_threshold,
            "positive_streak": result.positive_streak,
            "negative_streak": result.negative_streak,
            "positive_detections_required": result.positive_required,
            "negative_detections_required": result.negative_required,
            "poll_interval_seconds": self.coordinator.update_interval.total_seconds()
            if self.coordinator.update_interval
            else None,
            "ffmpeg_timeout_seconds": self.coordinator.ffmpeg_timeout,
            "ollama_timeout_seconds": self.coordinator.ollama_timeout,
            "last_error": result.error,
        }


class SentryBoxBinarySensorEntity(SentryBoxEntity, BinarySensorEntity):
    """Typed base class for SentryBox binary sensors."""


class SentryBoxSensorEntity(SentryBoxEntity, SensorEntity):
    """Typed base class for SentryBox sensors."""
