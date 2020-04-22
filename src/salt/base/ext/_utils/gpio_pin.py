
from RPi.GPIO import BOARD


MODE = BOARD

AMP_ON     = 31  # GPIO06

RPI_PWR    = 7   # GPIO04

STN_PWR    = 32  # GPIO12 only on SPM 1.X (high = SPM on/awake, low = SPM off/sleeping)
RPI_SHUTDN = 22  # GPIO25 only on SPM 2.X (high = perform shutdown, low = keep running)

LED        = 32  # GPIO12 only on SPM 2.X

ACC_INT1   = 29  # GPIO05

SPI_CLK    = 36  # GPIO16
SPI_MOSI   = 11  # GPIO17
SPI_MISO   = 38  # GPIO20

HOLD_PWR   = 33  # GPIO13
SPM_RESET  = 37  # GPIO26