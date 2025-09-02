"""Support for miramode ble sensors."""
from __future__ import annotations

import logging
import dataclasses

from .miramode import MiraModeState

from homeassistant import config_entries
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_ELECTRIC
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MiraModeCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MiraMode BLE sensors."""

    coordinator: MiraModeCoordinator = hass.data[DOMAIN][entry.entry_id]
    

    entities = [MiraModeWaterHeater(coordinator)]
    async_add_entities(entities)
    
class MiraModeWaterHeater(CoordinatorEntity[MiraModeCoordinator], WaterHeaterEntity):
    """Water Heater entity for Mira Mode device."""

    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_operation_list = [STATE_ELECTRIC]
    _attr_current_operation = STATE_ELECTRIC
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 25
    _attr_max_temp = 50
    _attr_name = "Water Temperature"
    _attr_icon = "mdi:coolant-temperature"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator
    ) -> None:
        """Populate the miramode entity with relevant data."""
        super().__init__(coordinator)

        device = coordinator.data
        name = f"{device.name}"

        self._attr_unique_id = f"{name}_temperature"

        self._id = device.address
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    device.address,
                )
            },
            name=name,
            manufacturer="Mira Showers",
            model="Mira Mode"
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature of the device."""
        return self.coordinator.data.temperature if self.coordinator.data else None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature of the device (is same as temperature for shower)."""
        return self.coordinator.data.temperature if self.coordinator.data else None

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperature on the device."""
        temperature = kwargs.get("temperature")
        if temperature is not None:
            await self.coordinator._async_set_temperature(temperature)

    @property
    def is_on(self) -> bool:
        """Return True if either shower or bath is active."""
        data = self.coordinator.data
        if data:
            return data.shower or data.bath
        return False
