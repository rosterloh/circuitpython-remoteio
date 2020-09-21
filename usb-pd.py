try:
    import os
    os.environ["BLINKA_MCP2221"]
except:
    print("Please set the BLINKA_MCP2221 environment variable before running")
    import sys
    sys.exit()

import board
from stusb4500 import STUSB4500

print("*** STUSB4500 controller via {} ***".format(board.board_id))

i2c = board.I2C()
pd = STUSB4500(i2c)