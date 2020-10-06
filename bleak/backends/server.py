"""
Base clase for backend servers.

Created on 2019-07-03 by kevincar <kevincarrolldavis@gmail.com>

"""

import abc
import asyncio
import logging
from typing import Any
from asyncio import AbstractEventLoop

from bleak.exc import BleakError
from bleak.backends.characteristic import GattCharacteristicsFlags

LOGGER = logging.getLogger(__name__)

class BaseBleakServer(abc.ABC):
    """
    The Server Interface for Bleak Backend
    """

    def __init__(self, loop: AbstractEventLoop = None, **kwargs):
        self.loop = loop if loop else asyncio.get_event_loop()

        self.services = None 
        self.read_request_func = None
        self.write_request_func = None

    # Async Context managers

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    @abc.abstractmethod
    async def start(self, **kwargs) -> bool:
        """
        Start the server

        Returns:
            Boolean - Whether server started successfully
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def stop(self) -> bool:
        """
        Stop the server

        Returns:
            Boolean - Whether the server stopped successfully
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def is_connected(self) -> bool:
        """
        Determine whether there are any connected peripheral devices
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def is_advertising(self) -> bool:
        """
        Determine whether the server is advertising
        """

    @abc.abstractmethod
    async def add_new_service(self, _uuid: str):
        """
        Generate a new service to be associated with the server
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def add_new_characteristic(self, service_uuid: str, char_uuid: str, properties: GattCharacteristicsFlags, value: bytearray, permissions: int):
        """
        Generate a new characteristic to be associated with the server
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def updateValue(self, service_uuid: str, char_uuid: str) -> bool:
        """
        Update the characteristic value. This is different than using
        characteristic.set_value. This send notifications to subscribed
        central devices.
        """
        raise NotImplementedError()

    def read_request(self, uuid: str) -> bytearray:
        """
        Obtain the characteritic to read and pass on to the user-defined
        read_request_func
        """
        characteristic = self.services.get_characteristic(uuid)
        if not characteristic:
            raise BleakError("Invalid characteristic: {}".format(uuid))

        return self.read_request_func(characteristic, server=self)

    def write_request(self, uuid: str, value: Any):
        """
        Obtain the characteristic to write and pass on to the user-defined
        write_request_func
        """
        characteristic = self.services.get_characteristic(uuid)
        self.write_request_func(characteristic, value, server=self)
