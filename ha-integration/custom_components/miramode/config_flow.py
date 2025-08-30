"""Config flow for MiraMode BlE integration."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from .miramode import MiraModeBluetoothDeviceData, MiraModeDevice
from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)    


class MiraModeConnectionError(Exception):
    """Custom error class for device when failing to connect."""


class MiraModeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MiraMode BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: BluetoothServiceInfo | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfo] = {}
        self._pending_entry_title: str | None = None
        self._pending_entry_data: dict | None = None

    async def _check_connection(self, bt_info: BluetoothServiceInfo) -> MiraModeDevice:
        """Check connection to device."""
        
        ble_device = bluetooth.async_ble_device_from_address(self.hass, bt_info.address)
        
        if ble_device is None:
            _LOGGER.debug("no ble_device in _get_device_data")
            raise MiraModeConnectionError("No ble_device")

        try:
            client = await establish_connection(BleakClient, ble_device, ble_device.address)
            await client.disconnect()
        except BleakError as err:
            _LOGGER.error("Error connecting to %s: %s", bt_info.address, err, )
            raise MiraModeConnectionError("Failed connecting to device") from err
        except Exception as err:
            _LOGGER.error("Unknown error occurred from %s: %s", bt_info.address, err)
            raise err

    async def async_step_bluetooth(self, bt_info: BluetoothServiceInfo) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered BT device: %s", bt_info)
        await self.async_set_unique_id(bt_info.address)
        self._abort_if_unique_id_configured()

        try:
            await self._check_connection(bt_info)
        except MiraModeConnectionError:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="unknown")

        self.context["title_placeholders"] = {"name": bt_info.name}
        self._discovered_device = bt_info

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            self._pending_entry_title = self.context["title_placeholders"]["name"]
            self._pending_entry_data = {
                CONF_ADDRESS: self._discovered_device.address,
            }
            return await self.async_step_device_details()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]

            self._discovered_device = discovery
            self._pending_entry_title = discovery.name
            self._pending_entry_data = {CONF_ADDRESS: address}

            return await self.async_step_device_details()

        # Discover devices...
        current_addresses = self._async_current_ids()
        for bt_info in async_discovered_service_info(self.hass):
            address = bt_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            if bt_info.name is None:
                continue
            if not bt_info.name.startswith("Mira"):
                continue

            try:
                await self._check_connection(bt_info)
            except MiraModeConnectionError:
                return self.async_abort(reason="cannot_connect")
            except Exception:
                return self.async_abort(reason="unknown")

            self._discovered_devices[address] = bt_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: discovery.name for (address, discovery) in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )

    async def async_step_device_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask user for device_id and client_id."""
        if user_input is not None:
            # Merge pending data with entered values
            data = {**self._pending_entry_data, **user_input}
            return self.async_create_entry(title=self._pending_entry_title, data=data)

        schema = vol.Schema(
            {
                vol.Required("device_id"): int,
                vol.Required("client_id"): int,
            }
        )
        return self.async_show_form(step_id="device_details", data_schema=schema)
