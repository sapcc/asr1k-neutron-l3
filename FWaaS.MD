## Problem
The OpenStack FWaaS API shall be implemented using the ASR1k/C8500 routers as backend. Configuration that largely complies with the requirements stated by the API needs to be found.

### Major OpenStack Feature Requirements
*Some features of the FWaaS Blueprint do not seem to be implemented. That includes all firewall address group and service group features.*
* Statefull Firewall
* Firewall Groups can be bound on any Neutron router port no matter if it is internal or external
* Firewall Policies can be bound either in ingress or egress direction


## ASR Feature: [Zone based Policy Firewall](https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/sec_data_zbf/configuration/xe-17/sec-data-zbf-xe-17-book/m_sec-zone-pol-fw-xe.html)


### Links
[Stateful ICMP](https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/sec_data_zbf/configuration/xe-17/sec-data-zbf-xe-17-book/m_fw-stateful-icmp.html)

[ZBF T-Shoot Guide](https://www.cisco.com/c/en/us/support/docs/security/ios-firewall/117721-technote-iosfirewall-00.html#anc11)

### Scaling Limitations

* > Configure zone-based firewall on the device such that the TCP traffic flow does not exceed 65k in the window size.
* > On the Cisco ASR 1000 Series Aggregation Services Routers the firewall supports a maximum of 4000 zones.
* > On the Cisco ASR 1000 Series Aggregation Services Routers the firewall supports a maximum of 1000 policy maps and 8 classes inside a policy map. You can configure a maximum of 16 match statements in a class map and 1000 globally.

### IOS XE CLI Configuration
[See here](fwaas_ios_config.md)