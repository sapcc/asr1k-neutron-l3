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

## CLI Configuration for an external interface Firewall Policy

Configuration:

```
ip access-list extended ACL-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN
 10 permit tcp any any eq www
 20 permit udp any any eq domain
 30 permit icmp any any echo

ip access-list extended ACL-FWAAS-7e2a161a85fd454f8838bc4de9563333-IN2OUT
 10 permit ip any any

parameter-map type inspect-vrf PAM-FWAAS-FWAAS-POLICE-VRF
 session total 1000000
 tcp syn-flood limit 2000
  
parameter-map type inspect-global
 log dropped-packets
 icmp-unreachable-allow
  no application-inspect all
 inspect vrf 7e2a161a85fd454f8838bc4de9563333 PAM-FWAAS-FWAAS-POLICE-VRF
 zone-mismatch drop

class-map type inspect match-all CM-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN
 match access-group name ACL-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN

class-map type inspect match-all CM-FWAAS-7e2a161a85fd454f8838bc4de9563333-IN2OUT
 match access-group name ACL-FWAAS-7e2a161a85fd454f8838bc4de9563333-IN2OUT


policy-map type inspect PM-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN
 class type inspect CM-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN
  inspect
 class class-default
  drop log
  
policy-map type inspect PM-FWAAS-7e2a161a85fd454f8838bc4de9563333-IN2OUT
 class type inspect CM-FWAAS-7e2a161a85fd454f8838bc4de9563333-IN2OUT
  inspect 
 class class-default
  drop log
  
zone security ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-in
zone security ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-out

zone-pair security ZP-FWAAS-7e2a161a85fd454f8838bc4de9563333-IN2OUT source ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-in destination ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-out
 service-policy type inspect PM-FWAAS-7e2a161a85fd454f8838bc4de9563333-IN2OUT
zone-pair security ZP-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN source ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-out destination ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-in
 service-policy type inspect PM-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN
 
 
interface BD-VIF6856
 zone-member security ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-in
 redundancy rii 6856
 redundancy group 1 decrement 1
interface BD-VIF7154
 zone-member security ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-in
 redundancy rii 7154
 redundancy group 1 decrement 1
interface BD-VIF7005
 zone-member security ZN-FWAAS-7e2a161a85fd454f8838bc4de9563333-out
 redundancy rii 7005
 redundancy group 1 decrement 1
```

Verification:
```
show policy-map type inspect zone-pair ZP-FWAAS-7e2a161a85fd454f8838bc4de9563333-IN2OUT
show policy-map type inspect zone-pair ZP-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN
show ip access-lists ACL-FWAAS-7e2a161a85fd454f8838bc4de9563333-OUT2IN
show policy-firewall sessions platform session detail
```