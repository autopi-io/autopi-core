class CANException(Exception):
    None

class CANDisallowedByConfigurationWarning(CANException):
    None

class CANMessageTooLongToAutoFormatException(CANException):
    None

class CANStrictQueryException(CANException):
    None

class CANWarning(Warning):
    None

class CANDisallowedByConfigurationWarning(CANWarning):
    None