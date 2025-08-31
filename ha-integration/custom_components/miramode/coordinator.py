import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .miramode import MiraModeBluetoothAPI, MiraModeState
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MiraModeCoordinator(DataUpdateCoordinator[MiraModeState]):
    """DataUpdateCoordinator for Mira Mode device."""

    def __init__(self, hass, address: str, client_id: str, device_id: str) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self._client = MiraModeBluetoothAPI(_LOGGER, hass, address, client_id, device_id)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @property
    def client(self) -> MiraModeBluetoothAPI:
        """Expose the underlying client for sending commands."""
        return self._client

    async def _async_update_data(self) -> MiraModeState:
        """Fetch latest data from Mira Mode device."""
        return await self._client.update_state()
        
    async def _async_set_temperature(self, temperature: float) -> MiraModeState:
        """Set temperature on the device and refresh data."""
        self.data = await self._client.set_temperature(temperature)
        self.async_set_updated_data(self.data)
        
        return self.data
        
    async def _async_set_shower(self, shower: bool) -> MiraModeState:
        """Set shower state for device and refresh data."""
        self.data = await self._client.set_shower(shower)
        self.async_set_updated_data(self.data)
        
        return self.data
        
    async def _async_set_bath(self, bath: bool) -> MiraModeState:
        """Set shower state for device and refresh data."""
        self.data = await self._client.set_bath(bath)
        self.async_set_updated_data(self.data)
        
        return self.data
