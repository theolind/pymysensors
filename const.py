"""
MySensors Constants
"""

#Msg: node-id;child-sensor-id;message-type;ack;sub-type;payload\n
#Ex: 24;0;1;0;23;53
# node 24
# child sensor 0
# set
# no ack
# light level

message_type = [
    'presentation',
    'set',
    'req',
    'internal',
    'stream',
]

sensor_type = [
    'S_DOOR',
    'S_MOTION',
    'S_SMOKE',
    'S_LIGHT',
    'S_DIMMER',
    'S_COVER',
    'S_TEMP',
    'S_HUM',
    'S_BARO',
    'S_WIND',
    'S_RAIN',
    'S_UV',
    'S_WEIGHT',
    'S_POWER',
    'S_HEATER',
    'S_DISTANCE',
    'S_LIGHT_LEVEL',
    'S_ARDUINO_NODE',
    'S_ARDUINO_RELAY',
    'S_LOCK',
    'S_IR',
    'S_WATER',
    'S_AIR_QUALITY',
    'S_CUSTOM',
    'S_DUST',
    'S_SCENE_CONTROLLER',
]

value_type = [
    'V_TEMP',
    'V_HUM',
    'V_LIGHT',
    'V_DIMMER',
    'V_PRESSURE',
    'V_FORECAST',
    'V_RAIN',
    'V_RAINRATE',
    'V_WIND',
    'V_GUST',
    'V_DIRECTION',
    'V_UV',
    'V_WEIGHT',
    'V_DISTANCE',
    'V_IMPEDANCE',
    'V_ARMED',
    'V_TRIPPED',
    'V_WATT',
    'V_KWH',
    'V_SCENE_ON',
    'V_SCENE_OFF',
    'V_HEATER',
    'V_HEATER_SW',
    'V_LIGHT_LEVEL',
    'V_VAR1',
    'V_VAR2',
    'V_VAR3',
    'V_VAR4',
    'V_VAR5',
    'V_UP',
    'V_DOWN',
    'V_STOP',
    'V_IR_SEND',
    'V_IR_RECEIVE',
    'V_FLOW',
    'V_VOLUME',
    'V_LOCK_STATUS',
    'V_DUST_LEVEL',
    'V_VOLTAGE',
    'V_CURRENT',
]

internal_type = [
    'I_BATTERY_LEVEL',
    'I_TIME',
    'I_VERSION',
    'I_ID_REQUEST',
    'I_ID_RESPONSE',
    'I_INCLUSION_MODE',
    'I_CONFIG',
    'I_FIND_PARENT',
    'I_FIND_PARENT_RESPONSE',
    'I_LOG_MESSAGE',
    'I_CHILDREN',
    'I_SKETCH_NAME',
    'I_SKETCH_VERSION',
    'I_REBOOT',
    'I_GATEWAY_READY',
]