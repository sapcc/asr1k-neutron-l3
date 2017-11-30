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

When not explicity specified any intellectual property manifested in this repository is subject to the following:  

    Copyright 2017 SAP SE

    All Rights Reserved.

    Licensed under the Apache License, Version 2.0 (the "License"); you may
    not use this file except in compliance with the License. You may obtain
    a copy of the License at

         http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
    License for the specific language governing permissions and limitations
    under the License.