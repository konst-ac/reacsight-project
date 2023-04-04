
## imports
from pymodbus.client.sync import ModbusTcpClient
import serial
from time import sleep, time
import requests

## communication constants
wago_address = {'ip':'192.168.0.102', 'port':502}
turbi_arduino_addresses = {1:'COM17', 2:'COM15', 4:'COM13'} #, 3:'COM18'
leds_address = 'http://localhost:5000'
# ot2_address = 'http://169.254.56.89:5000' Changed by Sara on 31/01/2022, after a failed calibration
# ot2_address = 'http://169.254.191.132:5000' Changed by Sara on 31/01/2022, after a restart of the PC
ot2_address = 'http://169.254.6.20:5000'
# ot2_address = 'http://169.254.118.20:5000'
guava_address = 'http://10.21.78.9:5000' #'http://157.99.244.170:5000'

# the class representing the device object
class Device:

    def __init__(self, use_wago_only=False, fake_OT2=False, connect_at_creation=True):
        self.connected = False
        self.use_wago_only = use_wago_only
        self.fake_OT2 = fake_OT2
        self.connect_at_creation = connect_at_creation
        if self.connect_at_creation:
            self.connect()

    def connect(self):
        self.wago = ModbusTcpClient(host=wago_address['ip'], port=wago_address['port'])
        if not self.use_wago_only:
            self.turbi_arduinos = {reactor_set_id:serial.Serial(turbi_arduino_addresses[reactor_set_id], 9600, timeout=10) \
                                    for reactor_set_id in turbi_arduino_addresses}
            sleep(2.) # needed before any serial write
        self.is_connected = True

    def disconnect(self):
        self.wago.close()
        if not self.use_wago_only:
            for turbi_arduino in self.turbi_arduinos.values():
                turbi_arduino.close()
        self.is_connected = False


    ## mapping pump slot id to coil
    def coil_of_pump(self, pump_slot_id):
        idx = int(pump_slot_id[1:])
        chr = pump_slot_id[0]
        if chr=='H':
            return (idx-1)*2
        elif chr=='L':
            return (idx-1)*2 + 1

    ## mapping valve id to coil
    def coil_of_valve(self, valve_id):
        idx = int(valve_id[1:])
        chr = valve_id[0]
        if chr=='B':
            return 32 + 16 + idx - 1
        elif chr=='F':
            return 32 + idx - 1

    ## generic coil reading returning None if no response
    def read_coil(self, coil_address):
        coil_response = self.wago.read_coils(coil_address, 1)
        if hasattr(coil_response, 'bits'):
            return coil_response.bits[0]
        else:
            return None

    ## commands
    def send_pump_command(self, pump_slot_id, pump_state):
        self.wago.write_coil(0x0200 + self.coil_of_pump(pump_slot_id), pump_state)

    def read_pump_state(self, pump_slot_id):
        return self.read_coil(0x0200 + self.coil_of_pump(pump_slot_id))

    def send_valve_command(self, valve_id, valve_state):
        self.wago.write_coil(0x0200 + self.coil_of_valve(valve_id), valve_state)

    def read_valve_state(self, valve_id):
        return self.read_coil(0x0200 + self.coil_of_valve(valve_id))

    def send_turbidity_command(self, reactor_set_id):
        self.turbi_arduinos[reactor_set_id].write(bytearray([100]))

    def receive_turbidity_readings(self, reactor_set_id):
        board_id = self.turbi_arduinos[reactor_set_id].read()[0]
        if board_id != reactor_set_id:
            raise Exception('Talking to wrong OD board( %i instead of %i). COM ports issue ?' % (board_id,reactor_set_id))
        readings = {}
        for i in range(4):
            reading = self.turbi_arduinos[reactor_set_id].read(2)
            reading = float(reading[0]*0x100+reading[1])
            readings[4*(reactor_set_id-1)+i+1] = reading
        return readings

    def read_all_coils(self):
        coil_response = self.wago.read_coils(0x0200,52)
        if hasattr(coil_response, 'bits'):
            return coil_response.bits
        else:
            return None

    def send_coils_shutoff_command(self):
        self.wago.write_coils(0x0200,[False]*52)

    def leds_request(self, endpoint):
        return requests.get(f'{leds_address}/{endpoint}').content.decode()

    def ot2_request(self, endpoint):
        if self.fake_OT2:
            return 'fake OT2 !'
        return requests.get(f'{ot2_address}/{endpoint}').content.decode()

    def guava_request(self, endpoint, is_file=False):
        if not is_file:
            return requests.get(f'{guava_address}/{endpoint}').text
        return requests.get(f'{guava_address}/{endpoint}').content
