"""The SentryBox integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_ENTRY_ID, DOMAIN, PLATFORMS, SERVICE_REANALYZE_NOW
from .coordinator import SentryBoxCoordinator

LOGGER = logging.getLogger(__name__)
SentryBoxConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SentryBox integration."""
    hass.data.setdefault(DOMAIN, {})

    if not hass.services.has_service(DOMAIN, SERVICE_REANALYZE_NOW):

        async def _handle_reanalyze(call: ServiceCall) -> None:
            entry_id = call.data.get(ATTR_ENTRY_ID)
            coordinators: dict[str, SentryBoxCoordinator] = hass.data.get(DOMAIN, {})

            if entry_id:
                coordinator = coordinators.get(entry_id)
                if coordinator is None:
                    LOGGER.warning("Service call referenced unknown entry_id %s", entry_id)
                    return
                hass.async_create_task(coordinator.async_request_refresh())
                return

            for coordinator in coordinators.values():
                hass.async_create_task(coordinator.async_request_refresh())

        hass.services.async_register(
            DOMAIN,
            SERVICE_REANALYZE_NOW,
            _handle_reanalyze,
            schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string}),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SentryBoxConfigEntry) -> bool:
    """Set up SentryBox from a config entry."""
    coordinator = SentryBoxCoordinator(hass, entry)
    entry.runtime_data = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await _async_remove_legacy_image_entity(hass, entry)
    await coordinator.async_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SentryBoxConfigEntry) -> bool:
    """Unload a SentryBox config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_remove_legacy_image_entity(
    hass: HomeAssistant, entry: SentryBoxConfigEntry
) -> None:
    """Remove the legacy image entity after migrating to a camera entity."""
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.domain == "image" and entity.unique_id.endswith("last_analysis_frame"):
            entity_registry.async_remove(entity.entity_id)
