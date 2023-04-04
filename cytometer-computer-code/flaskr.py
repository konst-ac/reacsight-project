from flask import Flask, request, redirect, url_for, render_template, send_file
import guava_clicking
import guava_file_service
from time import sleep
file_service = None

app = Flask(__name__)

@app.route('/')
def welcome():
    return 'Hello, this is the guava flask server'

@app.route('/prepare/<wells>/<int:n_events>')
def prepare_acquisition(wells,n_events):
    wells = wells.split('_')
    guava_clicking.prepare_acquisition(wells, n_events)
    sleep(8)
    return 'Done'

@app.route('/acquire')
def acquire():
    file_service.declare_ongoing_acquisition()
    guava_clicking.acquire()
    return 'Started acquisition, done when data !'

@app.route('/status')
def give_status():
    return file_service.status

@app.route('/retrieve_data')
def retrieve_data():
    if file_service.status == 'finished':
        file_to_send = send_file(file_service.raw_file)
        file_service.status = 'ready'
        return file_to_send

@app.route('/toggle_tray')
def toggle_tray():
    guava_clicking.toggle_tray()
    sleep(12)
    return 'Done'


@app.route('/start_file_service')
def start_file_service():
    global file_service
    if file_service is not None and file_service.is_alive():
        return 'File service already running'
    file_service = guava_file_service.Service()
    file_service.start()
    return 'File service started'
