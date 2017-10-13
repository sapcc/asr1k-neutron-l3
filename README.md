# asr1k-neutron-l3
Cisco ASR 1000 Neutron L3 driver
## ML2 Implementation
The ML2 part of the driver implementation is responsible for creating and managing l2 adjacencies between multiple L3 router interfaces and external L2 networks.

### Requirements

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

  
## L3 Core Functions

### Requirements

  * The implementation must support multiple routers per external network
  * The implementation must support multiple routers per internal Network
  * Multiple Subnets must be supported on external and internal networks
  * The implementation must not use additional resources in neutron for bookkeeping efforts (hiden Routers / hidden Ports)
  * Neutron provided information must match on device configuration (Port mac must match BVI mac etc.)
  * HA for box to box failover must be available 
  * HA failover of individual neutron routers is desirable but not mandatory, group based or global failover is sufficient
  * HA must not use additional network resources not assigned to the customer neutron router instance (IP's mac's etc.)

### Neutron Example Router
Router

```json
{
    "router": {
        "admin_state_up": true,
        "availability_zone_hints": [],
        "availability_zones": [
            "nova"
        ],
        "description": "",
        "distributed": false,
        "external_gateway_info": {
            "enable_snat": true,
            "external_fixed_ips": [
                {
                    "ip_address": "172.24.4.6",
                    "subnet_id": "b930d7f6-ceb7-40a0-8b81-a425dd994ccf"
                },
                {
                    "ip_address": "2001:db8::9",
                    "subnet_id": "0c56df5d-ace5-46c8-8f4c-45fa4e334d18"
                }
            ],
            "network_id": "ae34051f-aa6c-4c75-abf5-50dc9ac99ef3"
        },
        "ha": false,
        "id": "f8a44de0-fc8e-45df-93c7-f79bf3b01c95",
        "name": "HCP Example Project Router1",
        "revision_number": 1,
        "routes": [
            {
                "destination": "179.24.1.0/24",
                "nexthop": "172.24.3.99"
            }
        ],
        "status": "ACTIVE",
        "project_id": "7e02058126cc4950b75f9970368ba177",
        "tenant_id": "0bd18306d801447bb457a46252d82d13"
    }
}
```
External Port

```json
{
    "port": {
        "admin_state_up": true,
        "allowed_address_pairs": [],
        "created_at": "2016-03-08T20:19:41",
        "data_plane_status": "ACTIVE",
        "description": "",
        "device_id": "f8a44de0-fc8e-45df-93c7-f79bf3b01c95",
        "device_owner": "network:router_gateway",
        "extra_dhcp_opts": [],
        "fixed_ips": [
            {
                "ip_address": "172.24.4.6",
                "subnet_id": "a0304c3a-4f08-4c43-88af-d796509c97d2"
            }
        ],
        "id": "46d4bfb9-b26e-41f3-bd2e-e6dcc1ccedb2",
        "mac_address": "fa:16:3e:23:fd:d7",
        "name": "",
        "network_id": "a87cc70a-3e15-4acf-8205-9b711a3531b7",
        "port_security_enabled": false,
        "project_id": "7e02058126cc4950b75f9970368ba177",
        "security_groups": [],
        "status": "ACTIVE"
    }
}

{
    "network": {
        "id": "4e8e5957-649f-477b-9e5b-f1f75b21c03c",
        "mtu": 1500,
        "name": "net1",
        "qos_policy_id": "6a8454ade84346f59e8d40665f878b2e",
        "router:external": true,
        "segments": [
            {
                "provider:network_type": "vlan",
                "provider:physical_network": "segment1",
                "provider:segmentation_id": 1756
            },
            {
                "provider:network_type": "vlan",
                "provider:physical_network": "segment2",
                "provider:segmentation_id": 1890
            }
        ],
        "subnets": [
            "a0304c3a-4f08-4c43-88af-d796509c97d2"
        ],
        "vlan_transparent": false,
    }
}

{
    "subnet": 
        {
            "name": "external-subnet",
            "network_id": "4e8e5957-649f-477b-9e5b-f1f75b21c03c",
            "allocation_pools": [
                {
                    "start": "172.24.4.6",
                    "end": "172.24.4.254"
                }
            ],
            "host_routes": [],
            "ip_version": 4,
            "gateway_ip": "172.24.4.1",
            "cidr": "172.24.4.0/24",
            "id": "a0304c3a-4f08-4c43-88af-d796509c97d2",
            "description": "",
            "service_types": [],
            "subnetpool_id": null,
        }
}
```

Internal Port

```json
{
    "port": {
        "admin_state_up": true,
        "allowed_address_pairs": [],
        "created_at": "2016-03-08T20:19:41",
        "data_plane_status": "ACTIVE",
        "description": "",
        "device_id": "f8a44de0-fc8e-45df-93c7-f79bf3b01c95",
        "device_owner": "network:router_gateway",
        "extra_dhcp_opts": [],
        "fixed_ips": [
            {
                "ip_address": "10.180.0.1",
                "subnet_id": "b6704c3a-4f08-4c43-88af-d796569c97d2"
            }
        ],
        "id": "cdb6f71c-8de5-4918-9b5e-1a55fa96200e",
        "mac_address": "fa:16:3e:13:17:16",
        "name": "",
        "network_id": "ca82acc6-22d0-4b9f-86fd-5f2c0df22e04",
        "port_security_enabled": false,
        "project_id": "7e02058126cc4950b75f9970368ba177",
        "security_groups": [],
        "status": "ACTIVE"
    }
}

{
    "network": {
        "id": "ca82acc6-22d0-4b9f-86fd-5f2c0df22e04",
        "mtu": 1500,
        "name": "net1",
        "qos_policy_id": "6a8454ade84346f59e8d40665f878b2e",
        "router:external": true,
        "segments": [
            {
                "provider:network_type": "vlan",
                "provider:physical_network": "segment1",
                "provider:segmentation_id": 1356
            },
            {
                "provider:network_type": "vlan",
                "provider:physical_network": "segment2",
                "provider:segmentation_id": 1894
            }
        ],
        "subnets": [
            "b6704c3a-4f08-4c43-88af-d796569c97d2"
        ],
        "vlan_transparent": false,
    }
}

{
    "subnet": 
        {
            "name": "external-subnet",
            "network_id": "4e8e5957-649f-477b-9e5b-f1f75b21c03c",
            "allocation_pools": [
                {
                    "start": "10.180.0.6",
                    "end": "10.180.0.254"
                }
            ],
            "host_routes": [],
            "ip_version": 4,
            "gateway_ip": "10.180.0.1",
            "cidr": "10.180.0.0/24",
            "id": "ca82acc6-22d0-4b9f-86fd-5f2c0df22e04",
            "description": "",
            "service_types": [],
            "subnetpool_id": null,
        }
}

```

######VRF Definition per Router
```
vrf definition f8a44de0fc8e45df93c7f79bf3b01c95
 description HCP Example Project Router1
 !
 address-family ipv4
 exit-address-family
!
```

######External Router Port
Router with SNAT=false

```
interface BDI4501
 description 46d4bfb9-b26e-41f3-bd2e-e6dcc1ccedb2
 mac-address fa16.3e23.fdd7
 mtu 8950
 vrf forwarding f8a44de0fc8e45df93c7f79bf3b01c95
 ip nat outside
 ip address 172.24.4.6 255.255.255.0
 redundancy rii 10
 
ip route vrf f8a44de0fc8e45df93c7f79bf3b01c95 0.0.0.0 0.0.0.0 172.24.4.1
```

Router with SNAT=true

```
ip access-list extended nat-all
 permit ip any any

interface BDI4501
 description 46d4bfb9-b26e-41f3-bd2e-e6dcc1ccedb2
 mac-address fa16.3e23.fdd7
 mtu 8950
 vrf forwarding f8a44de0fc8e45df93c7f79bf3b01c95
 ip nat outside
 ip address 172.24.4.6 255.255.255.0
 redundancy rii 10
 
ip route vrf f8a44de0fc8e45df93c7f79bf3b01c95 0.0.0.0 0.0.0.0 172.24.4.1

ip nat pool f8a44de0fc8e45df93c7f79bf3b01c95 172.24.4.6 172.24.4.6 netmask 255.255.255.0
ip nat inside source list nat-all pool redundancy 1 mapping-id 10 vrf f8a44de0fc8e45df93c7f79bf3b01c95 overload

```

Router with SNAT=true with address scope support

```
ip access-list extended f8a44de0fc8e45df93c7f79bf3b01c95
 permit ip any any

interface BDI4501
 description 46d4bfb9-b26e-41f3-bd2e-e6dcc1ccedb2
 mac-address fa16.3e23.fdd7
 mtu 8950
 vrf forwarding f8a44de0fc8e45df93c7f79bf3b01c95
 ip nat outside
 ip address 172.24.4.6 255.255.255.0
 redundancy rii 10
 
ip route vrf f8a44de0fc8e45df93c7f79bf3b01c95 0.0.0.0 0.0.0.0 172.24.4.1

ip nat pool f8a44de0fc8e45df93c7f79bf3b01c95 172.24.4.6 172.24.4.6 netmask 255.255.255.0
ip nat inside source list f8a44de0fc8e45df93c7f79bf3b01c95 pool redundancy 1 mapping-id 10 vrf f8a44de0fc8e45df93c7f79bf3b01c95 overload

```

######Internal Router Port
Router with Address scope External != Address scope internal

```
interface BDI4502
 description cdb6f71c-8de5-4918-9b5e-1a55fa96200e
 mac-address fa16.3e13.1716
 mtu 8950
 vrf forwarding f8a44de0fc8e45df93c7f79bf3b01c95
 ip nat inside
 ip address 10.180.0.1 255.255.255.0
 
```

Router with Address scope External == Address scope internal

```
ip access-list extended f8a44de0fc8e45df93c7f79bf3b01c95
 deny   ip 172.24.5.0 0.0.0.255 any
 permit ip any any

interface BDI4502
 description cdb6f71c-8de5-4918-9b5e-1a55fa96200e
 mac-address fa16.3e13.1716
 mtu 8950
 vrf forwarding f8a44de0fc8e45df93c7f79bf3b01c95
 ip nat inside
 ip address 172.24.5.1 255.255.255.0
```

######Floating IP

```json
{
    "floatingips": [
        {
            "router_id": "f8a44de0-fc8e-45df-93c7-f79bf3b01c95",
            "description": "for test",
            "floating_network_id": "376da547-b977-4cfe-9cba-275c80debf57",
            "fixed_ip_address": "10.180.0.3",
            "floating_ip_address": "172.24.5.228",
            "port_id": "ce705c24-c1ef-408a-bda3-7bbd946164ab",
            "id": "2f245a7b-796b-4f26-9cf9-9e82d248fda7"
        }
     ]
}
```

Option assigned as secondary IP on outside Interface

```
interface BDI4501
 description 46d4bfb9-b26e-41f3-bd2e-e6dcc1ccedb2
 mac-address fa16.3e23.fdd7
 mtu 8950
 vrf forwarding f8a44de0fc8e45df93c7f79bf3b01c95
 ip nat outside
 ip address 172.24.4.6 255.255.255.0
 ip address 172.24.5.228 255.255.255.0 secondary
 redundancy rii 10

ip nat inside source static 10.180.0.3 172.24.5.228 vrf f8a44de0fc8e45df93c7f79bf3b01c95 redundancy 1 mapping-id 112

```

Option assigned as arp-alias

```
arp vrf f8a44de0fc8e45df93c7f79bf3b01c95 172.24.5.228 fa16.3e23.fdd7 arpa alias

ip nat inside source static 10.180.0.3 172.24.5.228 vrf f8a44de0fc8e45df93c7f79bf3b01c95 redundancy 1 mapping-id 112

```

######Open Architecture Topics:

 * Can we assign interfacce routes inside a vrf?
 * Does arp alias work for off-subnet ip's?
 * Do we need rii on interfaces or is mapping-id sufficient on nat statements ?
 * should/must all mapping-id's be the same or different for a given neutron router ? 

######Configuration Limits for resources:

| Resource | ID Space | ID Sope | Specific Limit | Global Limit | Requirements |
| ------------- |:-------------:|:----:| -----:|-----:|:-----|
| vrf | string | global | 8.000 | ??? |  one per Neutron virtual router | 
| secondary IP's | - | - | ??? | ??? |  one per Floating IP | 
| static NAT | - | - | ??? | ??? |  one per Floating IP |
| NAT Pool | string | global | ??? | ??? |  one per Neutron virtual router |
| dynamic NAT | string | global | ??? | ??? |  one per Neutron virtual router |
| rii | 1-65.000 | global | ??? | ??? |  one per Neutron Port |
| mapping-id | 1-2.147.483.647 | ??? | ??? | ??? |  one per TBD |
| arp alias| - | - | ??? | ??? |  one per Neutron Floating IP |
| static route | - | - | ??? | ??? |  one per Neutron virtual router + Extra Routes|
| access-lists | string | global | 4.000 | ??? |  one per Neutron virtual router |
| access-list entries | - | - | 400.000 | ??? |  one per Neutron virtual router + One Per Subnet in the same scope |



######Conventions:

  * **vrf name**: must match neutron router id, "-" must be removed from router id fit string length restrictions
  * **description**: Either neutron name, neutron description or name+description TBD??

######Resulting Scale Limitations
  * **Neutron Networks**: 8000 Neutron Routers per device

