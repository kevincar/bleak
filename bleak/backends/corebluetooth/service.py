import logging

from typing import List, Union

from Foundation import CBService, CBUUID, NSStringFromClass

from bleak.exc import BleakError
from bleak.backends.corebluetooth.characteristic import (
    BleakGATTCharacteristicCoreBluetooth,
)
from bleak.backends.service import (
    BleakGATTService, BleakGATTServiceCollection
)
from bleak.backends.characteristic import BleakGATTCharacteristic

logger = logging.getLogger(name=__name__)


class BleakGATTServiceCoreBluetooth(BleakGATTService):
    """GATT Service implementation for the CoreBluetooth backend"""

    def __init__(self, obj: CBService):
        super().__init__(obj)
        self.__characteristics: List[BleakGATTCharacteristic] = []

    # BleakGATTService abstract overrides

    @property
    def uuid(self) -> str:
        return self.obj.UUID().UUIDString()

    @property
    def characteristics(self) -> List[BleakGATTCharacteristic]:
        """List of characteristics for this service"""
        return self.__characteristics

    def get_characteristic(
        self, _uuid: str
    ) -> Union[BleakGATTCharacteristicCoreBluetooth, None]:
        """Get a characteristic by UUID"""
        try:
            return next(
                    filter(lambda x: x.uuid == _uuid.lower(), self.characteristics)
                    )
        except StopIteration:
            return None

    def add_characteristic(self, characteristic: BleakGATTCharacteristic):
        """Add a :py:class:`~BleakGATTCharacteristicDotNet` to the service.

        Should not be used by end user, but rather by `bleak` itself.
        """
        if characteristic in self.__characteristics:
            logger.warn(
                    "Service {} already has characteristic {}"
                    .format(self.uuid, characteristic.uuid)
                    )
            return

        self.__characteristics.append(characteristic)

        obj_class_name = NSStringFromClass(self.obj.class__())
        if obj_class_name == "CBMutableService":
            characteristics = list(
                    map(lambda x: x.obj, self.__characteristics)
                    )
            self.obj.setCharacteristics_(characteristics)
            logger.debug(
                    "Adding CBMutableCharacteristic {} to CBMutableService {}"
                    .format(characteristic.uuid, self.uuid)
                    )


class BleakGATTServiceCollectionCoreBluetooth(BleakGATTServiceCollection):
    """
    Simple data container for storing the peripheral's service complement.
    """

    def __init__(self):
        super(BleakGATTServiceCollectionCoreBluetooth, self).__init__()

    def add_characteristic(self, characteristic: BleakGATTCharacteristic):
        """Add a :py:class:`~BleakGATTCharacteristic` to the service collection.

        Should not be used by end user, but rather by `bleak` itself.
        """
        if characteristic.uuid not in self.characteristics:
            self.characteristics[characteristic.uuid] = characteristic
            self.services[characteristic.service_uuid].add_characteristic(
                    characteristic
                    )
        else:
            raise BleakError(
                "This characteristic is already present " +
                "in this BleakGATTServiceCollection!"
            )
