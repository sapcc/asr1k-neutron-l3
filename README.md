# asr1k-neutron-l3
Cisco ASR 1000 Neutron L3 driver
## ML2 Implementation
### Requirements
The ML2 part of the driver implementation is responsible for creating and managing l2 adjacencies between multiple L3 router interfaces and external L2 networks.

  * A 1:n relationship is required for router interfaces to external networks.
  * A 1:1 relationship between ASR interface and neutron virtual router must be maintained, sharing of interfaces is not allowed.
  * L2 interface creation and operation should be managed in an independent process from l3 configuration to allow for asynchronous operations.


### Traffic Flow Overview
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
### Neutron Network to IOS config Mapping
######Example Network:

```json
{
    "network": {
        "admin_state_up": true,
        "availability_zone_hints": [],
        "availability_zones": [
            "nova"
        ],
        "created_at": "2016-03-08T20:19:41",
        "dns_domain": "my-domain.org.",
        "id": "4e8e5957-649f-477b-9e5b-f1f75b21c03c",
        "mtu": 1500,
        "name": "net1",
        "port_security_enabled": true,
        "project_id": "9bacb3c5d39d41a79512987f338cf177",
        "qos_policy_id": "6a8454ade84346f59e8d40665f878b2e",
        "revision_number": 1,
        "router:external": false,
        "segments": [
            {
                "provider:network_type": "vlan",
                "provider:physical_network": "segment1",
                "provider:segmentation_id": 1235
            },
            {
                "provider:network_type": "vlan",
                "provider:physical_network": "segment2",
                "provider:segmentation_id": 1756
            }
        ],
        "shared": false,
        "status": "ACTIVE",
        "subnets": [
            "54d6f61d-db07-451c-9ab3-b9609b6b6f0b"
        ],
        "tenant_id": "4fd44f30292945e481c7b8a0c8908869",
        "updated_at": "2016-03-08T20:19:41",
        "vlan_transparent": false,
        "description": ""
    }
}
```
######Example Ports in Network:

```json
{
    "port": {
        "admin_state_up": true,
        "allowed_address_pairs": [],
        "description": "",
        "fixed_ips": [
            {
                "ip_address": "10.0.0.1",
                "subnet_id": "a0304c3a-4f08-4c43-88af-d796509c97d2"
            }
        ],
        "id": "46d4bfb9-b26e-41f3-bd2e-e6dcc1ccedb2",
        "mac_address": "fa:16:3e:23:fd:d7",
        "name": "",
        "network_id": "4e8e5957-649f-477b-9e5b-f1f75b21c03c",
        "port_security_enabled": false,
        "project_id": "7e02058126cc4950b75f9970368ba177",
        "status": "ACTIVE",
        "tenant_id": "7e02058126cc4950b75f9970368ba177"
    }
}
{
    "port": {
        "admin_state_up": true,
        "allowed_address_pairs": [],
        "description": "",
        "fixed_ips": [
            {
                "ip_address": "10.0.0.2",
                "subnet_id": "a0304c3a-4f08-4c43-88af-d796509c97d2"
            }
        ],
        "id": "6a8454ad-e843-46f5-9e8d-40665f878b2e",
        "mac_address": "fa:16:3e:23:ad:aa",
        "name": "",
        "network_id": "4e8e5957-649f-477b-9e5b-f1f75b21c03c",
        "port_security_enabled": false,
        "project_id": "7e02058126cc4950b75f9970368ba177",
        "status": "ACTIVE",
        "tenant_id": "7e02058126cc4950b75f9970368ba177"
    }
}
```

Config required per Neutron Network, added when the first port in the network is required on the Device, removed when the device no longer has ports in the respective network

###### Resulting Router Config
```
!External Interface for Neutron Networks (Config Option)
interface Port-channel1
 mtu 9000
 no ip address
 
 !Ethernet service endpoint one per neutron network
 service instance 1756 ethernet
  description 4e8e5957-649f-477b-9e5b-f1f75b21c03c
  encapsulation dot1q 1756
  rewrite ingress tag pop 1 symmetric
  bridge-domain 1756
 !

!Loopback Cable External Side 
interface Port-channel2
 mtu 9000
 no ip address
 
 !Ethernet service endpoint one per neutron port
 service instance 1 ethernet
  description 46d4bfb9-b26e-41f3-bd2e-e6dcc1ccedb2
  encapsulation dot1q 1756 second-dot1q 1
  rewrite ingress tag pop 2 symmetric
  bridge-domain 1756
 !
 service instance 2 ethernet
  description 6a8454ad-e843-46f5-9e8d-40665f878b2e
  encapsulation dot1q 1756 second-dot1q 2
  rewrite ingress tag pop 2 symmetric
  bridge-domain 1756
 !
 
!Loopback Cable Internal Side
interface Port-channel3
 mtu 9000
 no ip address
 
 !Ethernet service endpoint one per neutron port
 service instance 1 ethernet
  description 46d4bfb9-b26e-41f3-bd2e-e6dcc1ccedb2
  encapsulation dot1q 1756 second-dot1q 1
  rewrite ingress tag pop 2 symmetric
  bridge-domain 5001
 service instance 2 ethernet
  description 6a8454ad-e843-46f5-9e8d-40665f878b2e
  encapsulation dot1q 1756 second-dot1q 2
  rewrite ingress tag pop 2 symmetric
  bridge-domain 5002
```

######Configuration Limits for resources:

| Resource | ID Space | ID Sope | Specific Limit | Global Limit | Requirements |
| ------------- |:-------------:|:----:| -----:|-----:|:-----|
| Service Instance | 1-8000 | local | ??? | ??? |  External Interface: One Per Network<br /> Loopback Interface: One per Port | 
| Bridge-Domain | 1-16000 | global | ??? | ??? |  External Interface: One Per Network<br /> Loopback Interface: One per Port | 
| dot1q | 1-4096 | global | 4096 | ??? |  External Interface: One Per Network<br /> Loopback Interface: One per network |
| second-dot1q | 1-4096 | local | 4096 | ??? |  External Interface: - <br /> Loopback Interface: One per Port |

######Conventions:


  * **Bridge Domain**: <br />ID's 1-4096 are reserved for usage on the external interface, bridge-domain ID matches VLAN id of neutron segment ID<br /> Allocaton on internal side ID > 4097 mapping TBD<br /> Port-channel1.BD-ID == Port-channel2.BD-ID != Port-channel3.BD-ID.
  * **dot1q**: First VLAN Tag on loopback interfaces match the associated neutron network segment VLAN ID.
  * **second-dot1q**: Secondary tag on loopbacks need to be unique per Port per primary dot1q, allocation TBD.
  * **Service instance ID**:<br /> External Portchannel: instanceID == dot1q <br /> Loopback Portchannel: TBD

######Resulting Scale Limitations
  * **Neutron Networks**: 4096 Neutron Networks per device
  * **Neutron Ports**: 8000 Neutron Ports per device, 4096 Ports per Network

  
## L3 Implementation