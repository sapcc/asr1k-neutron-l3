# asr1k-neutron-l3
Cisco ASR 1000 Neutron L3 driver

# Traffic Flow Overview
```
                                                                         + +
                                                                Neutron  | |  Neutron
                                                                ML2      | |  L3
                                                                         | |
  UPLINK                           LoopBack                              | |
                                                                         | |
    ^                     +-----------------------+                      | |
    |                     |                       |                      | |
    |                     |                       |                      | |
+-------+             +---v---+               +---v---+                  | |
|  PO1  |             |  PO2  |               |  PO3  |                  | |
|TE  0-3|             |TE  4-5|               |TE  6-7|                  | |
+-------+             +-^-----+               +-------+                  | |
    |                   |   |                   |   |                    | |   +--------------+
    |         VLAN 10.1 |   |                   |   |          +---v---+ | |   | BDI 101      |
    |                   |   |                   |   | VLAN 10.1| BD 101| | |   | VRF Neutron1 |
    |      +---v--------+   |                   |   +---------->       +-------> 10.47.0.3    |
    |      | BD 10 |        |                   |              +-------+ | |   +--------------+
    +------>       |        |                   |                        | |
           +----------------+                   |                        | |
    VLAN 10         VLAN 10.2                   |              +---v---+ | |   +--------------+
                                                |     VLAN 10.2| BD 102| | |   | BDI 102      |
                                                +-------------->       +-------> VRF Neutron2 |
                                                               +-------+ | |   | 10.47.0.10   |
                                                                         | |   +--------------+
                                                                         | |
                                                                         | |
                                                                         | |
                                                                         | |
                                                                         | |
                                                                         + +
```
