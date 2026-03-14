"""Button platform for SentryBox."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DETECTION_PROMPT, DEFAULT_DETECTION_PROMPT
from .coordinator import SentryBoxCoordinator
from .entity import SentryBoxButtonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SentryBox buttons."""
    coordinator: SentryBoxCoordinator = entry.runtime_data
    async_add_entities([SentryBoxResetPromptButton(coordinator, entry)])


class SentryBoxResetPromptButton(SentryBoxButtonEntity):
    """Reset the prompt back to the built-in default."""

    _attr_name = "Reset Prompt"
    _attr_icon = "mdi:restore"

    def __init__(self, coordinator: SentryBoxCoordinator, entry: ConfigEntry) -> None:
        """Initialize the reset button."""
        super().__init__(coordinator, entry, "reset_prompt")

    async def async_press(self) -> None:
        """Reset the configured prompt and reload the entry."""
        new_options = dict(self._entry.options)
        new_options[CONF_DETECTION_PROMPT] = DEFAULT_DETECTION_PROMPT
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        await self.hass.config_entries.async_reload(self._entry.entry_id)
