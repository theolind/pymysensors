import mysensors.mysensors as mysensors

def event(type, nid):
    print(type+" "+str(nid))

gw = mysensors.SerialGateway('/dev/ttyACM0', event)
gw.debug = True
gw.start()
