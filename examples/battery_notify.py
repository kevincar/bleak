import asyncio
from bleak import BleakClient

address = "31EF2C41-7005-4195-846C-36CDB3B25619"
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"


async def run(address, loop):
    change = 0

    def battery_change(sender, value):
        battery_level = int.from_bytes(value, byteorder="little")
        print("Sender: {} set new value {}".format(sender, battery_level))
        change = 1  # noqa

    async with BleakClient(address, loop=loop, timeout=5.0) as client:
        await client.start_notify(BATTERY_LEVEL_UUID, battery_change)
        print("Awating battery level change")

        while change == 1:
            await asyncio.sleep(0.05)

        await client.stop_notify(BATTERY_LEVEL_UUID)
        print("Finished")

loop = asyncio.get_event_loop()
loop.run_until_complete(run(address, loop))
