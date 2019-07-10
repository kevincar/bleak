# -*- coding: utf-8 -*-
"""
Interface class for the Bleak representation of a GATT Characteristic

Created on 2019-03-19 by hbldh <henrik.blidh@nedomkull.com>

"""
from typing import List, Union

import asyncio

from asyncio import AbstractEventLoop

from System import Array, Byte, UInt64, Guid
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.descriptor import BleakGATTDescriptor
from bleak.backends.dotnet.descriptor import BleakGATTDescriptorDotNet

from bleak.backends.dotnet.utils import (
    wrap_Task,
    wrap_IAsyncOperation,
    IAsyncOperationAwaitable,
)

from Windows.Devices.Bluetooth.GenericAttributeProfile import GattCharacteristic

# Python representation of <class 'Windows.Devices.Bluetooth.GenericAttributeProfile.GattCharacteristicProperties'>
# TODO: Formalize this to Enum for all backends.
_GattCharacteristicsPropertiesEnum = {
    None: ("None", "The characteristic doesn’t have any properties that apply"),
    1: ("Broadcast".lower(), "The characteristic supports broadcasting"),
    2: ("Read".lower(), "The characteristic is readable"),
    4: (
        "Write-Without-Response".lower(),
        "The characteristic supports Write Without Response",
    ),
    8: ("Write".lower(), "The characteristic is writable"),
    16: ("Notify".lower(), "The characteristic is notifiable"),
    32: ("Indicate".lower(), "The characteristic is indicatable"),
    64: (
        "Authenticated-Signed-Writes".lower(),
        "The characteristic supports signed writes",
    ),
    128: (
        "Extended-Properties".lower(),
        "The ExtendedProperties Descriptor is present",
    ),
    256: ("Reliable-Writes".lower(), "The characteristic supports reliable writes"),
    512: (
        "Writable-Auxiliaries".lower(),
        "The characteristic has writable auxiliaries",
    ),
}


class BleakGATTCharacteristicDotNet(BleakGATTCharacteristic):
    """GATT Characteristic implementation for the .NET backend"""

    def __init__(self, obj: GattCharacteristic):
        super().__init__(obj)
        self.__descriptors = [
            # BleakGATTDescriptorDotNet(d, self.uuid) for d in obj.GetAllDescriptors()
        ]
        self.__props = [
            _GattCharacteristicsPropertiesEnum[v][0]
            for v in [2 ** n for n in range(10)]
            if (self.obj.CharacteristicProperties & v)
        ]
        self.__value = None

    def __str__(self):
        return "{0}: {1}".format(self.uuid, self.description)

    @property
    def service_uuid(self) -> str:
        """The uuid of the Service containing this characteristic"""
        return self.obj.Service.Uuid.ToString()

    @property
    def uuid(self) -> str:
        """The uuid of this characteristic"""
        return self.obj.Uuid.ToString()

    @property
    def description(self) -> str:
        """Description for this characteristic"""
        return self.obj.UserDescription

    @property
    def properties(self) -> List:
        """Properties of this characteristic"""
        return self.__props

    @property
    def descriptors(self) -> List[BleakGATTDescriptorDotNet]:
        """List of descriptors for this service"""
        return self.__descriptors

    def get_descriptor(self, _uuid) -> Union[BleakGATTDescriptorDotNet, None]:
        """Get a descriptor by UUID"""
        try:
            return next(filter(lambda x: x.uuid == _uuid, self.descriptors))
        except StopIteration:
            return None

    def add_descriptor(self, descriptor: BleakGATTDescriptor):
        """Add a :py:class:`~BleakGATTDescriptor` to the characteristic.

        Should not be used by end user, but rather by `bleak` itself.
        """
        self.__descriptors.append(descriptor)
        
    @property
    def value(self) -> bytearray:
        """Value of this characteristic"""
        return self.__value
    
    @value.setter
    def value(self, value: bytearray):
        """Set the value for the characteristic"""
        self.__value = value