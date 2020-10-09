"""
Example for publishing a service on a BLE 4.0 Server
"""

import logging
import asyncio
from bleak.backends.characteristic import GattCharacteristicsFlags
from bleak import BleakServer 

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(name=__name__)

my_service_name = "ECoGLink"
my_service_uuid = "A07498CA-AD5B-474E-940D-16F1FBE7E8CD"
my_characteristic_uuid = "51FF12BB-3ED8-46E5-B4F9-D64E2FEC021B"
my_characteristic_name = "mode"
my_characteristic_properties = GattCharacteristicsFlags.read.value | GattCharacteristicsFlags.write.value | GattCharacteristicsFlags.notify.value
my_characteristic_value = "AAAA"
my_characteristic_data = None
my_characteristic_permissions = 0x3


def read_char(char, server):
    print(char)


def write_char(char, value, server):
    print(char)


async def run(loop):
    server = BleakServer(name=my_service_name, loop=loop)
    # char = BleakGATTCharacteristic.new(my_characteristic_uuid, 0x2, bytearray(my_characteristic_value.encode()), 0x1)
    # service = BleakGATTService.new(my_service_uuid)
    # service.add_characteristic(char)
    await server.add_new_service(my_service_uuid)
    await server.add_new_characteristic(my_service_uuid, my_characteristic_uuid, my_characteristic_properties, None, my_characteristic_permissions)
    server.read_request_func = read_char
    server.write_request_func = write_char
    await server.start()
    await asyncio.sleep(20)

loop = asyncio.get_event_loop()
loop.run_until_complete(run(loop))
