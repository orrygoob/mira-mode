import asyncio
import binascii
import struct 
from bleak import BleakClient, BleakGATTCharacteristic

SHOWER_MAC = "3A2ECD87-2E4C-2585-E078-5BB0559B74DD"
SHOWER_CLIENT_ID = 32683
SHOWER_DEVICE_ID = 2
SHOWER_CHARACTERISTIC_UUID_READ = "bccb0003-ca66-11e5-88a4-0002a5d5c51b"
SHOWER_CHARACTERISTIC_UUID_WRITE = "bccb0002-ca66-11e5-88a4-0002a5d5c51b"

# Format - device_id + uuid_command + temperature + shower + bath = 01|87050101|e0|64|00 for shower
SHOWER_COMMAND = "87050101"
# Format - device_id + uuid_trigger_notif = 01|0700458A send to UUID_WRITE to trigger a notif on UUID_READ
SHOWER_TRIGGER_NOTIF = "0700458A"

# Use CRC-16-CCITT to validate payload, using the sniffed client id
def encode_crc(payload):
    data = payload + struct.pack(">I", SHOWER_CLIENT_ID)

    i = 0
    i2 = 0xFFFF
    while i < len(data):
        b = data[i]
        i3 = i2
        for i2 in range(8):
            i4 = 1
            i5 = 1 if ((b >> (7 - i2)) & 1) == 1 else 0
            if ((i3 >> 15) & 1) != 1:
                i4 = 0
            i3 = i3 << 1
            if (i5 ^ i4) != 0:
                i3 = i3 ^ 0x1021
        i += 1
        i2 = i3
    crc = i2 & 0xFFFF

    return payload + struct.pack(">H", crc)

_temperature = 40
_bath = False
_shower = False
    
def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    global _temperature, _bath, _shower
    print(f"Received message on {characteristic.uuid}: {binascii.hexlify(data)}")
    
    # Missing first byte but still contains data so pad to length
    if len(data) == 13:
        b = bytearray(b'\x00')
        data[0:0] = b
    
    if len(data) != 14:
        raise Exception("Unexpected data length")
            
    _temperature = round((data[6] + 268) / 10.4, 2)
    _shower = data[9] == 0x64
    _bath = data[10] == 0x64
    
    print(f"Temperature: {_temperature}, Shower: {_shower}, Bath: {_bath}")

async def main():
    
    print("Connecting...")
    async with BleakClient(SHOWER_MAC) as client:
        print(f"Connected: {client.is_connected}")

        print("Services discovered:")
        for service in client.services:
            print(service)

        # subscribe to notifications
        print("calling start_notify")
        await client.start_notify(SHOWER_CHARACTERISTIC_UUID_READ, notification_handler)
        await asyncio.sleep(2.0)
        
        # force a notification
        print("forcing notification")
        await client.write_gatt_char(SHOWER_CHARACTERISTIC_UUID_WRITE, bytes([SHOWER_DEVICE_ID]) + bytes.fromhex(SHOWER_TRIGGER_NOTIF))
        await asyncio.sleep(2.0)
        
        # toggle bath state and decrease temperature by 5 degrees
        print("toggling bath state and decreasing temperature")
        
        global _temperature, _bath, _shower
        _temperature -= 5
        _bath = not _bath
        
        temperatureHex = int(max(0, min(255, round(_temperature * 10.4 - 268))))
        showerHex = 0x64 if _shower else 0
        bathHex = 0x64 if _bath else 0
        payload = encode_crc(bytes([SHOWER_DEVICE_ID]) + bytes.fromhex(SHOWER_COMMAND) + bytes([temperatureHex, showerHex, bathHex]))
        await client.write_gatt_char(SHOWER_CHARACTERISTIC_UUID_WRITE, payload)
        await asyncio.sleep(2.0)
        
        print("calling stop_notify")
        await client.stop_notify(SHOWER_CHARACTERISTIC_UUID_READ)  

asyncio.run(main())
