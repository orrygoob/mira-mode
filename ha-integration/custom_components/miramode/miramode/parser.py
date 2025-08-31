"""Parser for MiraMode BLE devices"""

from __future__ import annotations

import asyncio
import dataclasses
import struct
from collections import namedtuple
from datetime import datetime
import logging

# from logging import Logger
from math import exp
from typing import Any, Callable, Tuple, TypeVar, cast

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

class BleakCharacteristicMissing(BleakError):
    """Raised when a characteristic is missing from a service."""


class BleakServiceMissing(BleakError):
    """Raised when a service is missing."""

    
class BleakNoResponse(BleakError):
    """Raised when an incorrect device id has been input and no response was heard."""

    
class BleakIncompatibleProduct(BleakError):
    """Raised when packets of the wrong length are being received."""

MIRA_CHARACTERISTIC_UUID_READ = "bccb0003-ca66-11e5-88a4-0002a5d5c51b"
MIRA_CHARACTERISTIC_UUID_WRITE = "bccb0002-ca66-11e5-88a4-0002a5d5c51b"

# Format - device_id + uuid_command + temperature + shower + bath = 01|87050101|e0|64|00 for shower
MIRA_COMMAND = "87050101"
# Format - device_id + uuid_trigger_notif = 01|0700458A send to UUID_WRITE to trigger a notif on UUID_READ
MIRA_TRIGGER_NOTIF = "0700458A"

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class MiraModeDevice:
    """Response data with information about the MiraMode device"""

    hw_version: str = ""
    sw_version: str = ""
    name: str = ""
    identifier: str = ""
    address: str = ""
    device_id: int = -1
    client_id: int = -1
    sensors: dict[str, str | float | None] = dataclasses.field(
        default_factory=lambda: {}
    )


# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
class MiraModeBluetoothAPI:
    """Data for MiraMode BLE sensors."""

    _event: asyncio.Event | None
    _command_data: bytearray | None

    def __init__(
        self,
        logger: Logger,
        client_id: int = 0, # only need to be set for control commands
        device_id: int = 0, # leave as optional for config flow so we can check connection to device before IDs are set
    ):
        super().__init__()
        self.logger = logger
        self.client_id = client_id
        self.device_id = device_id
        self._command_data = None
        self._event = None

    def notification_handler(self, _: Any, data: bytearray) -> None:
        """Helper for command events"""
        self._command_data = data

        if self._event is None:
            return
        self._event.set()

    def disconnect_on_missing_services(func: WrapFuncType) -> WrapFuncType:
        """Define a wrapper to disconnect on missing services and characteristics.

        This must be placed after the retry_bluetooth_connection_error
        decorator.
        """

        async def _async_disconnect_on_missing_services_wrap(
            self, *args: Any, **kwargs: Any
        ) -> None:
            try:
                return await func(self, *args, **kwargs)
            except (BleakServiceMissing, BleakCharacteristicMissing) as ex:
                logger.warning(
                    "%s: Missing service or characteristic, disconnecting to force refetch of GATT services: %s",
                    self.name,
                    ex,
                )
                if self.client:
                    await self.client.clear_cache()
                    await self.client.disconnect()
                raise

        return cast(WrapFuncType, _async_disconnect_on_missing_services_wrap)

    @disconnect_on_missing_services
    async def _get_state(self, client: BleakClient, device: MiraModeDevice) -> MiraModeDevice:

        self._event = asyncio.Event()
        try:
            await client.start_notify(
                MIRA_CHARACTERISTIC_UUID_READ, self.notification_handler
            )
        except:
            self.logger.warn("_get_state Bleak error 1")

        await client.write_gatt_char(MIRA_CHARACTERISTIC_UUID_WRITE, bytes([device.device_id]) + bytes.fromhex(MIRA_TRIGGER_NOTIF))

        # Wait for up to 10 seconds to see if a
        # callback comes in.
        try:
            await asyncio.wait_for(self._event.wait(), 10)
        except asyncio.TimeoutError:
            self.logger.warn("Timeout getting command data.")
        except:
            self.logger.warn("_get_state Bleak error 2")

        await client.stop_notify(MIRA_CHARACTERISTIC_UUID_READ)

        if self._command_data is None:
            self.logger.warn("Command data is None")
            raise BleakNoResponse("No response from device - is the Device ID correct?")
        elif len(self._command_data) != 13 and len(self._command_data) != 14:
            self.logger.warn("Unexpected data length %d", len(self._command_data))
            raise BleakIncompatibleProduct("Packets of the wrong length are being received - is this a MiraMode device?")
        else:
            # Missing first byte but still contains data so pad to length
            if len(self._command_data) == 13:
                b = bytearray(b'\x00')
                self._command_data[0:0] = b
            
            device.sensors["temperature"] = round((self._command_data[6] + 268) / 10.4, 2)
            device.sensors["shower"] = self._command_data[9] == 0x64
            device.sensors["bath"] = self._command_data[10] == 0x64
            self.logger.debug("Temperature: %s, Shower: %s, Bath: %s", device.sensors["temperature"], device.sensors["shower"], device.sensors["bath"])
            
        self._command_data = None
        return device

    async def update_device(self, ble_device: BLEDevice) -> MiraModeDevice:
        """Connects to the device through BLE and retrieves relevant data"""

        client = await establish_connection(BleakClient, ble_device, ble_device.address)
        device = MiraModeDevice()
        
        if ble_device.name.startswith("Mira N86Sd: "):
            device.name = ble_device.name.split(": ", 1)[1]
        else:
            device.name = ble_device.name
        
        device.identifier = ble_device.address
        device.address = ble_device.address
        device.client_id = self.client_id
        device.device_id = self.device_id

        device = await self._get_state(client, device)

        await client.disconnect()

        return device
