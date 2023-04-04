from flask import Flask, request, redirect, url_for, render_template
from time import time, sleep
from datetime import datetime
import serial
import threading
import logging
import logging.handlers

app = Flask(__name__)

intensities = {rid:0 for rid in range(1,17)}
schedule = {rid:{} for rid in range(1,17)}
history = {rid:[] for rid in range(1,17)}

arduino_1_8 = serial.Serial('COM16', 9600, timeout=10)
#arduino_9_16 = serial.Serial('COM16', 9600, timeout=10)
sleep(2.)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

rfh = logging.handlers.RotatingFileHandler(
    filename='LEDs.log',
    mode='a',
    maxBytes=3*1024*1024,
    backupCount=1000,
    encoding=None,
    delay=0)
logger.addHandler(rfh)

def send_led_command_to_arduino(reactor_id, intensity):
    if reactor_id < 9:
        arduino_1_8.write(bytearray([reactor_id+8, intensity]))
    else:
        pass
        #arduino_9_16.write(bytearray([reactor_id, intensity]))
    sleep(0.01)
    return 'done'

def led_schedule_worker():
    global intensities, schedule, history
    while True:
    # check if scheduled change
        for rid, changes in schedule.items():
            if changes:
                change_time, intensity = sorted(changes.items())[0]
                if change_time < time():
                    if intensity != intensities[rid]:
                        real_change_time = time()
                        real_change_datetime = datetime.now()
                        logger.info(f'{real_change_datetime} [{real_change_time}] reactor={rid} intensity={intensity}')
                        intensities[rid] = intensity
                        send_led_command_to_arduino(rid, intensity)
                        sleep(0.05)
                        history[rid].append((real_change_time, intensity))
                    del schedule[rid][change_time]
        # maintain
        for rid, intensity in intensities.items():
            send_led_command_to_arduino(rid, intensity)
            sleep(0.05)

led_schedule_thread = threading.Thread(target=led_schedule_worker)
led_schedule_thread.start()

@app.route('/')
def welcome():
    return 'Hello, this is the LED control flask server for InbioReactors'

@app.route('/reset_history')
def reset_history():
    global history
    history = {rid:[] for rid in range(1,17)}
    return 'done'

@app.route('/reset_schedule/<int:reactor_id>')
def reset_schedule(reactor_id):
    global schedule
    schedule[reactor_id] = {}
    return 'done'

@app.route('/turn_off_all')
def turn_off_all():
    global schedule
    for reactor_id in schedule:
        schedule[reactor_id] = {}
        schedule[reactor_id][time()] = 0
    while any([schedule[reactor_id]]):
        sleep(0.1)
    return 'done'

@app.route('/turn_on_all/<int:intensity>')
def turn_on_all(intensity):
    global schedule
    for reactor_id in schedule:
        schedule[reactor_id] = {}
        schedule[reactor_id][time()] = intensity
    while any([schedule[reactor_id]]):
        sleep(0.1)
    return 'done'

@app.route('/history/<int:reactor_id>')
@app.route('/history/<int:reactor_id>/<float:t_start>')
@app.route('/history/<int:reactor_id>/<int:t_start>')
def give_led_history(reactor_id, t_start=0.):
    result = ''
    for t_change,intensity in history[reactor_id]:
        if t_change > t_start:
            result += f'_{t_change}@{intensity}'
    return result

@app.route('/history/all')
@app.route('/history/all/<float:t_start>')
@app.route('/history/all/<int:t_start>')
def give_all_led_histories(t_start=0.):
    return '|'.join([give_led_history(rid, t_start) for rid in range(1,17)])


@app.route('/schedule/<int:reactor_id>/<int:intensity>')
@app.route('/schedule/<int:reactor_id>/<int:intensity>/<float:delta_t_seconds>')
@app.route('/schedule/<int:reactor_id>/<int:intensity>/<int:delta_t_seconds>')
def schedule_led_change(reactor_id, intensity, delta_t_seconds=0):
    global schedule
    schedule[reactor_id][time()+delta_t_seconds] = intensity
    return 'done'

@app.route('/schedule/sequence/<int:reactor_id>/<sequence_str>')
def schedule_led_change_sequence(reactor_id, sequence_str):
    global schedule
    t_now = time()
    changes = [(float(ch_str.split('@')[0]),int(ch_str.split('@')[1])) for ch_str in sequence_str.split('_')[1:]]
    for delta_t_seconds,intensity in changes:
        schedule_led_change(reactor_id, intensity, delta_t_seconds)
    return 'done'

@app.route('/duty_cycling/<int:reactor_id>/<int:intensity>/<float:period_seconds>/<float:fraction>/<int:cycle_number>')
@app.route('/duty_cycling/<int:reactor_id>/<int:intensity>/<int:period_seconds>/<float:fraction>/<int:cycle_number>')
@app.route('/duty_cycling/<int:reactor_id>/<int:intensity>/<int:period_seconds>/<int:fraction>/<int:cycle_number>')
@app.route('/duty_cycling/<int:reactor_id>/<int:intensity>/<float:period_seconds>/<int:fraction>/<int:cycle_number>')
def set_duty_cycle_schedule(reactor_id, intensity, period_seconds, fraction, cycle_number):
    global schedule
    # erase current schedule and turn off
    schedule[reactor_id] = {}
    schedule[reactor_id][time()] = 0
    # compute and add the new schedule
    if fraction == 0.:
        return 'done'
    t0 = time()
    if fraction == 1.:
        schedule[reactor_id][t0] = intensity
        schedule[reactor_id][t0+cycle_number*period_seconds] = 0
        return 'done'
    for n in range(cycle_number):
        schedule[reactor_id][t0+n*period_seconds] = intensity
        schedule[reactor_id][t0+n*period_seconds+fraction*period_seconds] = 0
    return 'done'
