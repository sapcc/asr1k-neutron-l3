# asr1k-neutron-l3
Cisco ASR 1000 Neutron L3 driver

The repository hosts an implementation of Openstack drivers to support L2 and L3 configuration of Cisco ASR1K devices to
provide the following Openstack extensions:

* Core L3 routing with HA support
* Quality of Service
* Firewall as a Service
* VPN as a Service

Documentation is split into two sections one mapping [Openstack Neutron entities to device configuration](DEVICE_README.md), the other 
describing the [design principles of the software components](DRIVER_README.md).  

**The current state in development/alpha and it is not intended for productive use in its current state**
