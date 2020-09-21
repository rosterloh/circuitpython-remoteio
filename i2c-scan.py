import os

if 'BLINKA_MCP2221' not in os.environ: 
    os.environ['BLINKA_MCP2221'] = '1'

import board

i2c = board.I2C()

while not i2c.try_lock():
    pass

print("I2C addresses found: {}".format([hex(device_address) for device_address in i2c.scan()]))
