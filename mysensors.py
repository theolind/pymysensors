import serial
import const

class Gateway:
    sensors = {}
    metric = True   #if true - use metric, if fales - use imperial

    # parse the data and respond to it appropriately
    # response is returned to the caller and has to be sent
    # data is a mysensors command string
    def logic(self, data):
        sMsg = Message(data)
        if sMsg.type == 'presentation':
            if sMsg.child_id == 255:
                # this is a presentation of the sensor platform
                # add sensor if it does not exist
                if sMsg.node_id not in self.sensors:
                    self.addSensor(sMsg.node_id)
                self.sensors[sMsg.node_id].type = sMsg.sub_type
                self.sensors[sMsg.node_id].version = sMsg.payload
            else:
                # this is a presentation of a child sensor
                self.sensors[sMsg.node_id].addChildSensor(sMsg.child_id, sMsg.sub_type)
        elif sMsg.type == 'set':
            self.sensors[sMsg.node_id].children[sMsg.child_id].value = sMsg.payload
        elif sMsg.type == 'internal':
            if sMsg.sub_type == 'I_ID_REQUEST':
                gMsg = Message()
                gMsg.node_id = sMsg.node_id
                gMsg.child_id = sMsg.child_id
                gMsg.type = 'internal'
                gMsg.ack = 0
                gMsg.sub_type = 'I_ID_RESPONSE'
                gMsg.payload = self.addSensor()
                return gMsg
            elif sMsg.sub_type == 'I_SKETCH_NAME':
                self.sensors[sMsg.node_id].sketch_name = sMsg.payload
            elif sMsg.sub_type == 'I_SKETCH_VERSION':
                self.sensors[sMsg.node_id].sketch_version = sMsg.payload
            elif sMsg.sub_type == 'I_CONFIG':
                gMsg = Message()
                gMsg.node_id = sMsg.node_id
                gMsg.child_id = sMsg.child_id
                gMsg.type = 'internal'
                gMsg.ack = 0
                gMsg.sub_type = 'I_CONFIG'
                gMsg.payload = 'M' if self.metric else 'I'
                return gMsg
        return None


    def addSensor(self, id = None):
        if id is None:
            for i in range(1, 254):
                if i not in self.sensors:
                    self.sensors[i] = Sensor(i)
                    return i
            return None
        else:
            if id not in self.sensors:
                self.sensors[id] = Sensor(id)
                return id
            else:
                return None


# serial gateway
class SerialGateway(Gateway):
    # provide the serial port
    def __init__(self, port):
        self.port = port

    # preferably start this in a new thread
    def listen(self):
        self.serial = serial.Serial(self.port, 115200)

        while True:
            s = self.serial.readline()
            r = super.logic(s.decode('utf-8'))
            if r is not None:
                self.send(r)

    def send(self, message):
        self.serial.write(message.encode())

#represents a sensor
class Sensor:
    children = {}
    id = None
    type = None
    sketch_name = None
    sketch_version = None

    def __init__(self, id):
        self.id = id

    def addChildSensor(self, id, type):
        self.children[id] = ChildSensor(id, type)


class ChildSensor:
    id = None
    type = None
    value = None

    def __init__(self, id, type):
        self.id = id
        self.type = type


#receives and parses a message, just provide the string
class Message:
    def __init__(self, data = None):
        if data is not None:
            self.decode(data)

    # decode a message from command string
    def decode(self, data):
        data = data[:-1].split(';')
        self.node_id = int(data[0])
        self.child_id = int(data[1])
        self.type = const.message_type[int(data[2])]
        self.ack = int(data[3])
        if self.type == 'presentation':
            self.sub_type = const.sensor_type[int(data[4])]
        elif self.type == 'set' or self.type == 'req':
            self.sub_type = const.value_type[int(data[4])]
        elif self.type == 'internal':
            self.sub_type = const.internal_type[int(data[4])]
        self.payload = data[5]

    # encode a command string from message
    def encode(self):
        ret = str(self.node_id) + ";" + str(self.child_id) + ";"
        ret += str(const.message_type.index(self.type)) + ";"
        ret += str(self.ack) + ";"
        if self.type == 'presentation':
            ret += str(const.sensor_type.index(self.sub_type)) + ";"
        elif self.type == 'set' or self.type == 'req':
            ret += str(const.value_type.index(self.sub_type)) + ";"
        elif self.type == 'internal':
            ret += str(const.internal_type.index(self.sub_type)) + ";"
        ret += str(self.payload) + "\n"
        return ret