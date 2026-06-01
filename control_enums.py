from enum import Enum

"""
This file houses all the enums used in the the control system
"""


class WellState(Enum):
    """
    This enum represents the 3 states a well can be in: Disabled, Manual or Calculated
    """
    DISABLED = 0
    MANUAL = 1
    CALCULATED = 2

    def next(self):
        """
        Cycles through the well state options
        :return: next WellState
        """
        return WellState((self.value + 1) % len(WellState))


class ControlStatus(Enum):
    """
    This enum represents the states the Machine can be in: Disabled, Manual or Calculated
    """
    IDLE = 0
    FEEDING = 1
    FLUSHING = 2
    STOPPING = 3


class PlateType(Enum):
    """
        This enum represents the plate types (i.e number of wells) by name
    """
    PLATE24 = "PLATE24"
    PLATE48 = "PLATE48"
