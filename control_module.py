from movement_driver import movement_driver
from fluidics_system import fluidics_module
from cv_system import cv_module


class ControlUnit:

    # todo: decide where all system data is stored and implement pull if needed
    def __init__(self):
        """
        Control Unit constructor. Creates movement system, fluidics system and CV objects.
        :return: ControlUnit object
        """
        try:
            self.fluidics_module = fluidics_module.FluidicsDriver()
            self.movement_module = movement_driver.MovementDriver()
            self.cv_module = cv_module()
        except:
            print("Subsystem initiation failed")
            exit(1)

    def __del__(self):
        """
        Control Unit destructor. Closes all module instances
        :return: VOID
        """
        # Close movement serial
        self.movement_module.__del__()
        self.cv_module.__del__()
        self.fluidics_module.__del__()
