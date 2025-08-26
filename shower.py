"""Platform for shower integration."""
from __future__ import annotations

import logging

from .mira import MiraInstance

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.climate import ClimateEntity
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger("mira")

# This is the BLE address of the device
# Obtain the mac, device_id, and client_id by sniffing the packets of an already paired device
mac_address = "3C877B91-23D1-46FB-8AA1-8DE3847449CE"
device_id = 2
client_id = 32683

controller = MiraInstance(mac_address, device_id, client_id)

class BathSwitch(SwitchEntity):
    """Representation of the bath valve switch."""

    def __init__(self):
        self._is_on = False

    @property
    def is_on(self):
        """Return true if bath is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn the bath on."""
        controller.bath_on()  # Call the method from your controller
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the bath off."""
        controller.bath_off()  # Call the method from your controller
        self._is_on = False
        self.schedule_update_ha_state()

    async def async_update(self):
        """Fetch the current state from the controller and update."""
        self._is_on = await controller.shower()
        self.schedule_update_ha_state()

class ShowerSwitch(SwitchEntity):
    """Representation of the shower valve switch."""

    def __init__(self):
        self._is_on = False

    @property
    def is_on(self):
        """Return true if the shower is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn the shower on."""
        controller.shower_on()
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the shower off."""
        controller.shower_off()
        self._is_on = False
        self.schedule_update_ha_state()

    async def async_update(self):
        """Fetch the current state from the controller and update."""
        self._is_on = await controller.shower()
        self.schedule_update_ha_state()

class ShowerBathClimate(ClimateEntity):
    """Representation of the temperature control setpoint only."""

    def __init__(self):
        self._target_temperature = None

    @property
    def temperature_unit(self):
        """Return the unit of measurement which is Celsius."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature from the controller."""
        return controller.temperature()

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return the HVAC mode (no modes, just temperature control)."""
        return None  # No heating/cooling control

    @property
    def hvac_modes(self):
        """Return a list of supported HVAC modes (empty in this case)."""
        return []

    def set_temperature(self, **kwargs):
        """Set the target temperature and propagate to the controller."""
        if 'temperature' in kwargs:
            self._target_temperature = kwargs['temperature']
            controller.set_temperature(self._target_temperature)
            self.schedule_update_ha_state()

    async def async_update(self):
        """Fetch the current target temperature from the controller."""
        self._target_temperature = await controller.temperature()
        self.schedule_update_ha_state()

# In the main integration setup, register these entities with Home Assistant
async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the bath valve, shower valve, and temperature control."""
    async_add_entities([BathValve(), ShowerValve(), ShowerBathClimate()])