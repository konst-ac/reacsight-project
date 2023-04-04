# import nidaqmx
# from time import sleep


# for i in range(20):
#     with nidaqmx.Task() as task:
#         task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
#         r = task.read()
#     print(r)
#     sleep(3)

import nidaqmx.system
system = nidaqmx.system.System.local()
print(system.driver_version)

for device in system.devices:
    print(device)

device = system.devices['Dev1']

phys_chan = device.ai_physical_chans['ai0']

print(phys_chan.ai_term_cfgs)
