import mysensors.mysensors as mysensors


def event(type, nid):
    print(type + " " + str(nid))

gw = mysensors.SerialGateway('/dev/ttyACM0', event, True)
gw.debug = True
gw.start()
# To set sensor 2, child 1, sub-type V_LIGHT (= 2), with value 1.
gw.set_child_value(2, 1, 2, 1)
gw.stop()
