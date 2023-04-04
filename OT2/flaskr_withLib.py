import os
os.system("systemctl stop opentrons-robot-server")

import opentrons
from opentrons import types
from opentrons.types import Point
from opentrons.drivers.smoothie_drivers import driver_3_0
import opentrons.execute
from opentrons.execute import get_protocol_api
import numpy as np
import json
from flask import Flask
from time import sleep

global_offset = {'x':-0.7, 'y':1.3, 'z': 0.5} # careful, zero is ignored

print(opentrons.__version__)
protocol = get_protocol_api('2.7')
protocol.home()

# create flask app
app = Flask(__name__)

def get_json(name, version=1):
    #path = f'/usr/lib/python3.7/site-packages/opentrons/protocols/labware/definitions'#/{version}'
    if version == 2:
        with open(f'{name}.json') as f:
            return json.load(f)
    if version == 2:
        with open(f'{path}/{name}/1.json') as f:
            return json.load(f)
    return 'not sup'

def get_json_with_offset(name, version=2, offset=None, load_name='custom-labware'):
    json_def = get_json(name, version)
    if 'parameters' not in json_def:
        json_def['parameters'] = {}
    json_def['parameters']['loadName'] = load_name
    if offset is not None:
        json_def['cornerOffsetFromSlot'] = offset
    return json_def

def add_labware(name, slot, version=2, offset=None, share=False):
    total_offset = global_offset.copy()
    if offset is not None:
        for c,v in offset.items():
            total_offset[c] += v
    container = protocol.load_labware_from_definition(
        get_json_with_offset(name=name,
                         version=version,
                         offset=total_offset,
                         load_name=f'{name}_{slot}_share-{share}'),
        location=str(slot))
    return container
    
def add_pipette_and_tips(tip_rack_slots):
    tip_racks = [protocol.load_labware('opentrons_96_tiprack_300ul', str(slot)) for slot in tip_rack_slots] 
    pipette = protocol.load_instrument('p300_multi', mount='right', tip_racks=tip_racks)
    return pipette

# ==========================================================================================================================

# define labware
pipette = add_pipette_and_tips(tip_rack_slots=[2])

#cytoplate = add_labware(name='corning_96_wellplate_360ul_flat', offset={'x': 129.3, 'y': -0.5, 'z':50.6}, slot=9)
cytoplate = add_labware(name='corning_96_wellplate_360ul_flat', offset={'x': 129, 'y': 7, 'z':50.6}, slot=9)

sampling_plate_pipette_1 = add_labware(name='corning_96_wellplate_360ul_flat',
                                       offset={'x':-0.6, 'y':0.6, 'z':118.5},
                                       slot=7)

sampling_plate_pipette_2 = add_labware(name='corning_96_wellplate_360ul_flat',
                                       offset={'x':-1.1, 'y':1.2, 'z':119},
                                       slot=10)

reservoir_1 = add_labware(name='nest_12_reservoir_15ml', slot=8)
reservoir_2 = add_labware(name='nest_12_reservoir_15ml', slot=11)
trash = add_labware(name='corning_96_wellplate_360ul_flat', offset={'x':125, 'y':7.5, 'z':119}, slot=3)

# --------------------------------------------------------------------------------------------------------------------------
# NEW STUFF 
# --------------------------------------------------------------------------------------------------------------------------

magdeck = protocol.load_module('magnetic module gen2', '4')
height_ref_mag = 6.0
mag_plate = magdeck.load_labware('biorad_96_wellplate_200ul_pcr')
mag_plate.set_offset(x=-0.7, y=0.55, z=0.00)

peltier = protocol.load_module('temperature module gen2', '1')
prep_plate = peltier.load_labware('opentrons_96_aluminumblock_biorad_wellplate_200ul')
prep_plate.set_offset(x=0.00, y=1.2, z=3.00)

# sampling_plate_pipette_3 = add_labware(name='corning_96_wellplate_360ul_flat',
#                                        offset={'x':-0.6, 'y':0.6, 'z':131.5},
#                                        slot=5)
sampling_plate_pipette_3 = add_labware(name='corning_96_wellplate_360ul_flat',
                                       offset={'x':-0.6, 'y':0.6, 'z':119},
                                       slot=5)

# --------------------------------------------------------------------------------------------------------------------------
# END NEW STUFF 
# --------------------------------------------------------------------------------------------------------------------------

labware_dictionary = {'sampling':sampling_plate_pipette_1,
                      'sampling_2':sampling_plate_pipette_2,
                      'sampling_3':sampling_plate_pipette_3,
                      'cytoplate':cytoplate,
                      'printed_trash':trash,
                      'trough':reservoir_1,
                      'magdeck' : magdeck,
                      'mag_plate' : mag_plate,
                      'prep_plate' : prep_plate}
                    
@app.route('/version')
def version():
    return('2.7')

@app.route('/gotobin')
def gotobin():
    pipette.move_to(trash['A1'].top())
    return 'done'

@app.route('/shakeit')
def shake():
    for i in range(3):
        pipette.move_to(trash['A1'].top())
        pipette.move_to(trash['A2'].top())
        pipette.move_to(trash['A1'].top())
    return('done')

@app.route('/tips/pick_up')
def tips_pick_up():
    pipette.pick_up_tip(presses=2)
    return('tips picked')

@app.route('/tips/drop')
def tips_drop():
    pipette.drop_tip()
    return('tips dropped')

@app.route('/tips/return')
def tips_return():
    pipette.return_tip()
    return('tips returned')

@app.route('/tips/reset')
def tips_reset():
    pipette.reset_tipracks()
    return('tips tracking reset')

@app.route('/blink/<int:number_of_blinks>')
def buttonglowblink(number_of_blinks):
    from time import sleep
    driver = driver_3_0.SmoothieDriver()
    
    for t in range(number_of_blinks):
        driver.turn_on_red_button_light()
        sleep(0.2)
        driver.turn_on_blue_button_light()
        sleep(0.2)
    return('successfully blinked')
  
@app.route('/dilute/<int:vol_sample>/<int:plate_num>/<int:col>')
def load_and_dilute_in_cytoplate(vol_sample, plate_num, col):
    if plate_num == 1:
        sp = sampling_plate_pipette_1
        res = reservoir_1
    elif plate_num == 2:
        sp = sampling_plate_pipette_2
        res = reservoir_2
    else:
        return 'invalid plate num'
    if not pipette.has_tip:
        pipette.pick_up_tip()
    pipette.transfer(
            200-vol_sample,
            res.columns_by_name()[str(col)],
            cytoplate.columns_by_name()['2'],
            new_tip='never')
    pipette.transfer(
            vol_sample,
            sp.columns_by_name()[str(col)],
            cytoplate.columns_by_name()['2'],
            new_tip='never',
            mix_after=(3, 100))
    gotobin()
    pipette.blow_out()
    return 'done'

# --------------------------------------------------------------------------------------------------------------------------
# NEW STUFF 
# --------------------------------------------------------------------------------------------------------------------------
# handling liquids 
@app.route('/transfer/<int:volume>/<string:labwareA>/<int:colA>/<string:labwareB>/<int:colB>/')
def transfer(volume,labwareA,colA,labwareB,colB):
    fr_labware = labware_dictionary[labwareA]
    to_labware = labware_dictionary[labwareB]
    pipette.transfer(volume,
                     fr_labware.columns_by_name()[str(colA)], 
                     to_labware.columns_by_name()[str(colB)],
                     new_tip='never',
                     mix_after=(3, 100))
    gotobin()#necessary !!! 
    #pipette.blow_out()
    return 'transfer done'


@app.route('/mix_beads_sample/<int:volume>/<int:colA>/<int:colB>')
def mix_beads_sample(volume,colA,colB):    
    #mixing sampled cells and mCer
    pipette.transfer(volume, 
                     sampling_plate_pipette_3.columns_by_name()[str(colA)], 
                     prep_plate.columns_by_name()[str(colB)], 
                     new_tip='never',
                     mix_after=(3, 100))
    pipette.transfer(volume, 
                     prep_plate.columns_by_name()[str(colB)], 
                     prep_plate.columns_by_name()[str(colA)], 
                     new_tip='never',
                     mix_after=(3, 100))    
    magdeck.disengage()
    
    # rough pipette : let's recover beads attached to wells
    pipette.flow_rate.aspirate = 300
    pipette.flow_rate.dispense = 500
    pipette.flow_rate.blow_out = 2000

    pipette.mix(5,100)
    pipette.blow_out()
    pipette.mix(5,100)
    pipette.blow_out()
        
    #load beads into the mag plate with standard pipette
    pipette.flow_rate.aspirate = 150
    pipette.flow_rate.dispense = 300
    pipette.flow_rate.blow_out = 1000
    
    pipette.transfer(volume, 
                     prep_plate.columns_by_name()[str(colA)], 
                     mag_plate.columns_by_name()[str(colA)], 
                     new_tip='never',
                     mix_after=(3, 100))
    
    gotobin()#necessary !!!
    return 'sample mix done'


@app.route('/wash_beads/<int:volume>/<int:colA>/<int:colB>')
def wash_beads(volume,colA,colB):
    
    del protocol.deck['2']
    tbs_tank = add_labware(name='nest_12_reservoir_15ml', slot=2)
    
    for i in range(1,4):
        magdeck.engage(height=height_ref_mag)
        
        #gentle pipette to gently mix beads so that they attached to the magnet
        pipette.flow_rate.aspirate = 50
        pipette.flow_rate.dispense = 50
        
        pipette.move_to(mag_plate['A' + str(colA)].top())
        pipette.mix(2, 50)
        sleep(5)

        #standard pipette for transfers
        pipette.flow_rate.aspirate = 150
        pipette.flow_rate.dispense = 300
    
        pipette.transfer(volume, 
                     mag_plate.columns_by_name()[str(colA)], 
                     trash.columns('1'), 
                     new_tip='never')
        pipette.blow_out()
        
        magdeck.disengage()
        
        pipette.transfer(volume, 
                     tbs_tank.columns_by_name()[str(colA)], 
                     mag_plate.columns_by_name()[str(colA)], 
                     new_tip='never',
                     mix_after=(3, 100))
        
        # rough pipette : let's recover beads attached to wells
        pipette.flow_rate.aspirate = 300
        pipette.flow_rate.dispense = 500
        pipette.flow_rate.blow_out = 2000
    
        pipette.mix(5,100)
        pipette.blow_out()
        pipette.mix(5,100)
        pipette.blow_out()
        
    #back to standard pipette
    pipette.flow_rate.aspirate = 150
    pipette.flow_rate.dispense = 300
    pipette.flow_rate.blow_out = 1000
    
    gotobin()#necessary !!! 
    return 'washings done' 

@app.route('/load_beads/<int:col>')
def load_beads(col):

    del protocol.deck['2']
    tbs_tank = add_labware(name='nest_12_reservoir_15ml', slot=2)

    #shake beads outta here (recover the attached beads from the mag deck)
    pipette.flow_rate.aspirate = 300
    pipette.flow_rate.dispense = 500
    pipette.flow_rate.blow_out = 2000
    
    pipette.mix(4, 100, mag_plate['A' + str(col)])
    pipette.blow_out()
    
    #back to standard pipette for transfer
    pipette.flow_rate.aspirate = 150
    pipette.flow_rate.dispense = 300
    pipette.flow_rate.blow_out = 1000
    
    # load the 100µL of beads into cytoplate            
    pipette.transfer(100, 
             mag_plate.columns_by_name()[str(col)], 
             cytoplate.columns_by_name()['1'], 
             new_tip='never',
             mix_after=(3, 100))        
    
    #complete the 100 µL of beads with TBS to have 200 µL in the cytometer 
    pipette.transfer(100, 
             tbs_tank.columns_by_name()[str(col)], 
             cytoplate.columns_by_name()['1'], 
             new_tip='never',
             mix_after=(3, 100))
    gotobin()
    return 'beads loaded'
  
@app.route('/blowout')
def blowout():
    pipette.blow_out()
    return 'blown out :)'
                   
# handling modules 
@app.route('/disengage/<string:module>')
def disengage(module):
    labware_dictionary[module].disengage()
    return 'disengaged'

@app.route('/engage/<float:height>')
def engage(height):
    magdeck.engage(height=height)
    return 'engaged'


@app.route('/set_temperature/<int:temp>/')
def set_temperature(temp):
    peltier.set_temperature(temp)
    return 'temperature set :) '


@app.route('/wash_row_beads/<int:col>')
def wash_cytoplate_row_2(col):
    
    del protocol.deck['2']
    tbs_tank = add_labware(name='nest_12_reservoir_15ml', slot=2)
    
    # NEW by Sara: try to wash beads in a better way by pipetting on the well border
    
    if not pipette.has_tip:
        pipette.pick_up_tip()
    else:
        gotobin()
        pipette.blow_out()
        
    #shake beads outta here (recover the attached beads from the cytoplate)
    pipette.flow_rate.aspirate = 500
    pipette.flow_rate.dispense = 700
    pipette.flow_rate.blow_out = 2000
    
    pipette.transfer(
            100,
            tbs_tank.columns(str(col)),
            cytoplate['A1'],
            new_tip='never',
            mix_after=(3, 100))
    
    # decrease a lot along x and y (about 10 times) increasing z at the same value (they are in mm/s)
    protocol.max_speeds['x'] = 50
    protocol.max_speeds['y'] = 50
    protocol.max_speeds['z'] = 250

    # rotate around the edge of the well
    destination = types.Location(cytoplate['A1'].from_center_cartesian(0.9,0,0.9), cytoplate['A1'])
    pipette.aspirate(200,cytoplate['A1'])
    pipette.dispense(200,destination)
    
    destination = types.Location(cytoplate['A1'].from_center_cartesian(0.9,0.9,0.9), cytoplate['A1'])
    pipette.aspirate(200,cytoplate['A1'])
    pipette.dispense(200,destination)
    
    destination = types.Location(cytoplate['A1'].from_center_cartesian(0,0.9,0.9), cytoplate['A1'])
    pipette.aspirate(200,cytoplate['A1'])
    pipette.dispense(200,destination)
    
    destination = types.Location(cytoplate['A1'].from_center_cartesian(-0.9,0.9,0.9), cytoplate['A1'])
    pipette.aspirate(200,cytoplate['A1'])
    pipette.dispense(200,destination)
    
    destination = types.Location(cytoplate['A1'].from_center_cartesian(-0.9,0,0.9), cytoplate['A1'])
    pipette.aspirate(200,cytoplate['A1'])
    pipette.dispense(200,destination)
    
    destination = types.Location(cytoplate['A1'].from_center_cartesian(-0.9,-0.9,0.9), cytoplate['A1'])
    pipette.aspirate(200,cytoplate['A1'])
    pipette.dispense(200,destination)
    
    destination = types.Location(cytoplate['A1'].from_center_cartesian(0,-0.9,0.9), cytoplate['A1'])
    pipette.aspirate(200,cytoplate['A1'])
    pipette.dispense(200,destination)
    
    destination = types.Location(cytoplate['A1'].from_center_cartesian(0.9,-0.9,0.9), cytoplate['A1'])
    pipette.aspirate(200,cytoplate['A1'])
    pipette.dispense(200,destination)
 
    # reset the original values for the velocities
    protocol.max_speeds['x'] = 600
    protocol.max_speeds['y'] = 400
    protocol.max_speeds['z'] = 125
    
    pipette.mix(5,100,cytoplate['A1'])
    pipette.blow_out()
    
    pipette.flow_rate.aspirate = 500
    pipette.flow_rate.dispense = 300
    pipette.flow_rate.blow_out = 2000
    
    pipette.transfer(
            250,
            cytoplate['A1'],
            trash.columns('1'),
            new_tip='never')
    pipette.blow_out()
    
    #back to standard pipette for transfer
    pipette.flow_rate.aspirate = 150
    pipette.flow_rate.dispense = 300
    pipette.flow_rate.blow_out = 1000
    
    return 'done'

# --------------------------------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------------------------------
@app.route('/wash_from_trough/<int:plate_num>/<int:col>')
def wash_cytoplate(plate_num,col):
    if plate_num == 1:
        res = reservoir_1
    elif plate_num == 2:
        res = reservoir_2
    else:
        return 'invalid plate num'
    if not pipette.has_tip:
        pipette.pick_up_tip()
    else:
        gotobin()
        pipette.blow_out()
    pipette.transfer(
            250,
            cytoplate.columns('2'),
            trash.columns('1'),
            new_tip='never')
    pipette.blow_out()
    pipette.transfer(
            200,
            res.columns(str(col)),
            cytoplate.columns('2'),
            new_tip='never',
            mix_after=(3, 100))
    pipette.transfer(
            250,
            cytoplate.columns('2'),
            trash.columns('1'),
            new_tip='never')
    pipette.blow_out()
    return 'done'


@app.route('/move_to/<string:labware>/<int:col_number>')
def moveto(labware,col_number): #moves to a labware's column
    if labware == 'sampling_metal':
        pipette.move_to(sampling_plate_pipette_1.well('A' + str(col_number)).top().move(types.Point(x=121, y=7, z=10)))
    elif labware == 'sampling_metal_2':
        pipette.move_to(sampling_plate_pipette_2.well('A' + str(col_number)).top().move(types.Point(x=121, y=7, z=10)))
    elif labware == 'sampling_metal_3':
        pipette.move_to(sampling_plate_pipette_3.well('A' + str(col_number)).top().move(types.Point(x=121, y=7, z=10)))  
    else:
        to_labware = labware_dictionary[labware]
        pipette.move_to(to_labware['A' + str(col_number)].top())
    return('done gotcha')

