import os

if 'BLINKA_MCP2221' not in os.environ: 
    os.environ['BLINKA_MCP2221'] = '1'

import board
from stusb4500 import STUSB4500

print("*** STUSB4500 controller via {} ***".format(board.board_id))

i2c = board.I2C()
pd = STUSB4500(i2c)
pd.read()

for i in range(1, 4):
    print("PDO{}: {} V, {} A".format(i, pd.get_voltage(i), pd.get_current(i)))

print("Current PDO: {}".format(pd.get_pdo_number()))
print("Flex Current: {} A".format(pd.get_flex_current()))