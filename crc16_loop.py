# 18561
# ('Success', 32683)
# On =  0287 0501 01E0 0064 D85B
# Off = 0287 0501 01E0 0000 4881

# device id = 0x02
# client id = 32683 (cracked from packet below)

import struct
import binascii

data = bytearray([
        0x02, 0x87,
        0x05, 0x01,
        0x01, 0xE0,
        0x00, 0x64])
payl = bytearray([
        0x02, 0x87,
        0x05, 0x01,
        0x01, 0xE0,
        0x00, 0x64,
        0xD8, 0x5B])
client = 0x00000000

def _crc(data):
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
    return i2 & 0xFFFF


def _get_payload_with_crc(payload, client_id):
    crc = _crc(payload + struct.pack(">I", client_id))
    print(crc)
    return payload + struct.pack(">H", crc)

while client < 0xFFFFFFFF:
	paylg = _get_payload_with_crc(data, client)
	if paylg == payl:
		print("Success", client)
		print(binascii.hexlify(paylg))
		break
	else:
		print("Wrong! ", client)
		client += 1
print("End")
