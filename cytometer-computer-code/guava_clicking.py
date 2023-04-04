
import pyautogui as ag
from time import time, sleep

ag.PAUSE = 0.2
ag.FAILSAFE = True

pos_edit_worklist = (81,126)
pos_close = (1387,502)
pos_run = (1382,460) # to find
pos_well_A1 = (903,419)
pos_well_H12 = (1250,658)
delta_col = (pos_well_H12[0] - pos_well_A1[0])/11.
delta_row = (pos_well_H12[1] - pos_well_A1[1])/7.
pos_acquire_sample = (617,457)
pos_events_number = (635,509)
pos_sample_id = (629,486)
pos_reset = (1380,543)
#pos_incyte_taskbar = (475,1055)
pos_search_settings = (1202,557)
pos_search_settings_desktop = (692,372)
pos_select_settings = (892,402)
pos_open_settings = (1209,687)
pos_acquire_worklist = (1187,724)
pos_run_worklist = (1000,618)
pos_eject_load_tray_worklist = (363,129)

row_map = {'A':0,'B':1,'C':2,'D':3,'E':4,'F':5,'G':6,'H':7}

def pos_well(well):
    row = row_map[well[0]]
    col = int(well[1:]) - 1
    return (pos_well_A1[0]+col*delta_col, pos_well_A1[1]+row*delta_row)

def toggle_tray():
    ag.click(*pos_eject_load_tray_worklist)

def prepare_acquisition(wells, n_events=5000):
    #ag.click(*pos_incyte_taskbar)
    ag.click(*pos_edit_worklist)
    ag.click(*pos_reset)
    for well in wells:
        ag.click(pos_well(well))
        ag.click(*pos_acquire_sample)
        ag.click(*pos_events_number, 3)
        ag.hotkey('del')
        ag.write(str(n_events))
    ag.click(*pos_run)
    ag.click(*pos_search_settings)
    ag.click(*pos_search_settings_desktop)
    sleep(1.)
    ag.click(*pos_select_settings)
    ag.click(*pos_open_settings)
    ag.click(*pos_acquire_worklist)

def acquire():
    ag.click(*pos_run_worklist)
