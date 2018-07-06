# asr1k-neutron-l3 drivers and agent

This document describes the software implementation of an Openstack ML2 driver and ML2 agent and L3 plug-in and L3 agent
 for Cisco ASR 1000 devices. The plug-in will eventually support the following features:
 
 * L3 Routing with SNAT support
 * L3 Extra Route and host routes
 * Firewall as a Service
 * QoS
 * BGP/MPLS VPN Interconnection
 * HA for all features across routing devices
 
## Installing and Running
 
On the Neutron server pod/host 
 
    pip intall git+https://github.com/sapcc/asr1k-neutron-l3.git#egg=asr1k_neutron_l3
    
    Copy  etc/neutron/plugins/ml2/ml2_conf_asr1k.ini to /etc/neutron/plugins/ml2/ml2_conf_asr1k.ini
    
    Adjust the physical network in /etc/neutron/plugins/ml2/ml2_conf_asr1k.ini to your needs
    
    In /etc/neutron/neutron conf :
        
        Add asr1k_neutron_l3.plugins.l3.service_plugins.asr1k_router_plugin.ASR1KRouterPlugin to the service plugin list
        
        Set router_scheduler_driver = asr1k_neutron_l3.plugins.l3.schedulers.simple_asr1k_scheduler.SimpleASR1KScheduler
    
    Apply DB migration :
        
        neutron-db-manage upgrade head
    
    Start the neutron server process  with --config-file /etc/neutron/plugins/ml2/ml2_conf_asr1k.ini

On the ASR L3 Agent server pod/host(s):
     
     pip intall git+https://github.com/sapcc/asr1k-neutron-l3.git#egg=asr1k_neutron_l3
     
     Copy  etc/neutron/asr1k.conf to /etc/neutron/devices.conf
     
     Adjust settings in /etc/neutron/asr1k.conf to your environment
    
     Start L3 agent process :
        
        asr1k-l3-agent --config-file /etc/neutron/neutron.conf  --config-file /etc/neutron/asr1k.conf
     
     Start ML2 agent process :   
        
        asr1k-ml2-agent --config-file /etc/neutron/neutron.conf  --config-file /etc/neutron/asr1k.conf
 
 
## Components 

                                            +------------------------------------------+              +--------------+
    +----------------------------+       +-------------------------------------------+ |            +--------------+ |
    |       Neutron Server       |       |               L3 Agent Host               | |            |  ASR Device  | |
    |                            |       |                                           | |            |     Pair     | |
    | +------------------------+ |       | +------------------+  +-------+ +-------+ | |            |              | |
    | |   Core L3 Extension    | |       | |  ASR1K L3 Agent  |  |   N   | |   R   | | |            |              | |
    | |                        | |       | |                  |  |   e   | |   e   | | |            |              | |
    | |                        | |       | |                  |  |   u   | |   s   | | |            |              | |
    | +------------------------+ |       | |                  |  |   t   | |   t   | | |            |              | |
    | |   ASR1K Driver Shim    | |       | +------------------+  |   r   | |       | | |            |              | |
    | |     ASR1K RPC API      | |       |                       |   o   | |   M   | | |   NetConf  |              | |
    | |   ASR1K Schedulers     | |  RPC  |                       |   n   | |   o   | | |    YANG    |              | |
    | +------------------------+ |------>|                       |       | |   d   | |------------->|              | |
    |                            |       |                       |   M   | |   e   | | | (SSH/WSMA) |              | |
    | +------------------------+ |       | +------------------+  |   o   | |   l   | | |            |              | |
    | |        Core ML2        | |       | |  ASR1K ML2 Agent |  |   d   | |   s   | | |            |              | |
    | |                        | |       | |                  |  |   e   | |       | | |            |              | |
    | |                        | |       | |                  |  |   l   | |       | | |            |              | |
    | +------------------------+ |       | |                  |  |   s   | |       | | |            |              | |
    | |         ASR1K          | |       | +------------------+  +-------+ +-------+ | |            |              | |
    | |    Mechanisn Driver    | |       |                                           | |            |              | |
    | |                        | |       |                                           | |            |              | |
    | +------------------------+ |       |                                           | |            |              | |
    |                            |       |                                           | +            |              | +
    +----------------------------+       +-------------------------------------------+              +--------------+


 
## Separation of L2 and L3 concerns
In the Neutron L3 reference implementation there is a clear separation of L2 and L3 configuration for virtual routers. 
 We would like to extend this concept to the ASR drivers with a mechanism layer 2 (ML2) driver handling the binding of 
 router ports and the resulting device configuration and the L3 plugin/extensions dealing with all L3 related device 
 configuration. 

At all times the Neutron port status should reflect the L2 state of the port binding. If the binding and/or device 
 configuration fails the port status should be 'Down'. Similarly, and if possible, the Neutron router status should 
 reflect the device configuration state with values ACTIVE, DEGRADED, DOWN reflecting fully functional, floating IP(FIP) 
 or extra route configuration failure and interface or other configuration failure respectively. 
  
## Use of Neutron L3 reference DB models

The core/reference Neutron L2 and L3 DB models such as ports,routers FIPs etc. should be used to define the supported 
 L3 scenarios. Additional DB models should be used sparingly and only when absolutely necessary to persist state 
 required to support the desired device configuration. 
 
The required device configuration has been explicitly designed to minimise additional state and to map a closely, as 
 possible, IOS configuration stanzas to Neutron models. For the basic routing scenario its anticipated that one 
 additional DB model will be required to map bridge domains and second dot1q tag to Neutron ports. Any additional
 DB model should, where possible, cascade delete via a foreign key reference. When this is not possible drivers/agents 
 should ensure periodic sanity checks of any additional tables to clean redundant entries. 
  
The driver/plugin and RPC implementations should be minimal and act as lightweight 'shims' to the reference 
 implementation. Core methods can be overridden to provide extended functionality if required , but the core functionality 
 and persistence models should be used. The approach is to reuse the core to benefit from community improvements/bugfixes 
 and make upgrading Neutron version as simple as possible. 
 
## High Availability/Redundancy/Scale
 
Based on the reuse of Neutron core L3 extensions it is intended that HA and redundancy is completely abstracted from 
 Neutron. Instead, the chassis based redundancy group capability of the ASR platform will be used to provide device 
 HA. 
   
A redundancy group is modelled as a pair of devices and a single L3 agent will be responsible for managing a HA pair. 
 Routers will be scheduled to an agent and the agent will manage the configuration of the two devices. The ML2 driver 
 and L3 plugin will not be aware of the devices nor will any device state or configuration be required by the Neutron 
 server process. For example the Neutron ports representing  router interfaces will be configured identically on each 
 device with no additional MAC or IP address needed to support HA.     
  
Horizontal scale will be achieved by deploying additional L3 agent hosts and device pairs. Scheduling is implemented
 via normal L3 schedulers. The specific scheduling algorithm are TBD, but most likely 'least used' will be implemented 
 based on the routers scheduled to available agents. 
    
## Device API 

The agents primarily communicate with devices via the Netconf/Yang API. Due to current   limitations
 in the Netconf API (e.g. ARP alias is  missing from the Yang model). Until these are 
 addressed in firmware updates the Yang configuration is augmented with SSH or WSMA. The desired end goal
 is that all required configuration can be applied via Netconf-YANG.
 
In general the following sequence of calls a made for an configuration update :

1. get-config for entity id
2. edit-config with merge operation for create/update
3. edit-config with delete operation for delete

The replace operation is used in some cased to replace entire entites, for example in the case of a route update an entire
 VRF's route list can be updated in a single API call. Further optimisation by 'batching' list updates via replace needs 
 investigation. 

The agent device API access is designed to act as a psuedo ORM implementation providing basic CRUD operations and 
 querying. Yang models are encapsulated in Python classes which can serialise/de-serialise the device configuration. The 
 Neutron entities are also abtracted into 'DTO' models which encapsulate the data and Yang models/actions required to
 transform the Neutron models to device configuration. It is intended in the final implementation that the Yang models
 will be able evaluate diffs between the Neutron and device state, both to report on inconsistencies and to minimise
 the number of API operations. 
   
Optimisation of API operations is somewhat complicated due to the nature of L3 Agent RPC notifications. It appears that
 for all L3 router changes (router: create, delete, update  interface: add, remove gateway: add, remove floating ip: 
 associate, disassociate, route: add, delete) the agent only receives a router updated or deleted notification. This
 means that for even the simplest change (e.g. router description) the entire router configuration across both devices
 in the pair has to be updated. Even with models capable of 'diffing' Neutron and the device it may be necessary to make
 multiple API requests to evaluate the diff. Further investigation is required to evaluate options to improve this. 
 
## Operational Considerations

Failure is inevitable, so we expect that at some point one or both devices with end up with configuration that differs
 from the Neutron DB. Neutron should be considered the source of truth regarding the configuration and the devices should
 be considered the source of truth regarding operational state. The following has been implemented to support operational
 and support/troubleshooting work.

 1. API tools to create, update, delete and validate the device configuration for a Neutron router based on the
  current Neutron state of entities. API can also be used to get expected config for L2/L3 interfaces, l3 interface statistics 
  and any orphaned device configuration.   
 2. The entity status in Neutron should reflect as closely as possible the status of the device configuration as described
  above
  
Further work should implement the following broad requirements:
  
 1. The agent and driver should be instrumented to provide metric for performance (e.g. API operation execution time)
  , scale (e.g. number of routers, floating IPs etc) and errors (e.g. API failures). Key metrics should be exposed via Promethesus   
 2. A seperate agent should be developed to gather metrics the operation state of the entities configured on the device. 
  For example gather SNMP data, subscribing to Netconf events (when available) or querying via API. Key metrics should again be
  exposed via Prometheus     
   
     
### ASR1K APIs

The following APIs have been integrated into the Neutron API. The PUT and DELETE operations should be used with caution. 
There is currently no CLI implementation so the APIs can only be used via a rest client, they were tested with 
[Postman](https://www.getpostman.com/apps). Use `openstack token issue` to generate an auth token (scoped to project that 
gives `cloud_network_admin` role) and set the `X-Auth-Token` request header. The following APIs should then be accessible
via the neutron V2.0  API endpoint  `http(s)://[neutron server FQDN/IP]:[port]/v2.0`  
 
|        |                                             |                                                                   |
|--------|---------------------------------------------|-------------------------------------------------------------------|
| GET    | `/asr1k/routers/[router-id]`                | Returns a json string showing any diffs between device configuration and that expected by Neutron.           |                       
| PUT    | `/asr1k/routers/[router-id]`                | Attempts to sync the neutron config to the devices                |
| DELETE | `/asr1k/routers/[router-id]`                | Removes the router config from the devices. **Use with caution**  |
| GET    | `/asr1k/config/[router-id]`                 | Returns a json string showing ASR1K specific configuration stored in Neutron, important when debugging L2 specific issues |                       
| PUT    | `/asr1k/config/[router-id]`                 | Creates ASR1K specific Neutron configuration. **Use with caution**|
| GET    | `/asr1k/orphans/[agent-host]`               | Returns a json string showing configuration regarded as redundant based on a check against Neutron. It uses pattern matching to identify potential candidates and cannot be guarenteed 100% accurate. |                      
| DELETE | `/asr1k/orphans/[agent-host]`               | Removes any orphaned configuration from the devices. ** Please check** all configuration returned by the GET method is indeed managed by the ASR1K driver before executing this method|
| GET    | `/asr1k/interface-statistics/[router-id]`   | Show L3 interface information and packet statistics for the  the Neutron router's interfaces on the devices.     |                       
| GET    | `/asr1k/devices/[agent-host]`               | Returns a json string showing device configuration on the agent. |                      
| PUT    | `/asr1k/device/[agent-host]`                | Use with a JSON body in format `{[device1_id]}:[enable][disable],[device2_id]}:[enable][disable]`  to enable or disable a specific device. Disabled means config will not be applied to the device  |
 

  
  
  
