# Control System

This repo contains our implementation of the control system. 
It includes the control_unit module, UI and logo.

## Dependencies - nees update

1. PySide6
2. enum

## Utils - nees update
Utils can be found in the movement_utils folder. They can be used for calibration, introduction of new commands and more. The current utils are:
1. command_sender: initiates the movement system, and then enable the user to send G-code directly to the movement_system.
2. predefined_plan: moves the movement system in a pre-built plan. Can be modified for different needs and scenarios.
3. keypress_controller: Creates a keyboard press based interface with the movement system. Useful for calibration. WORK IN PROGRESS, NOT VALIDATED YET

## Usage - nees update
IN THE FUTURE WILL BE USED BY CONTROL UNIT

## TODO's
1. logic so that feeds cannot hit each other
2. outline between feeds for better visibility
3. more feed information (i.e feed_id, time, name of project/batch etc)
4. load feed (for changes)
5. control panel add excel directory and photo directories


## Contributing - nees update

Asaf Shasha and Nitai Gildor
