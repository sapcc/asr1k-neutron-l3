# IOS CLI Config for FWaaS

## FWaaS policies bound on internal interfaces

When a firewall policy is bound on an internal router interfaces, we implement the firewall stateless, using IOS _extended access-lists_ (ACL). Stateful is unsupported due to the combinatorial explosion of `zones` that IOS requires to implement this feature. We would need to create a `zone-pair` for the every ingress and egress interface combination.

Below snippet shows the diff to a given virtual router or _VRF_ to apply the same ingress/egress OpenStack firewall policies on the two internal ports.

```diff
+ip access-list extended ACL-FWAAS-def33d0c-8831-46fa-b54c-f293b626a143
+ 1 permit tcp any any established
+ 2 permit icmp any any echo-reply
+ 3 permit icmp any any unreachable
+ 4 permit icmp any any time-exceeded
+ 5 permit icmp any any timestamp-reply
+ 10 permit tcp any any eq www
+ 20 permit udp any any eq domain
+ 30 permit icmp any any echo
+ 40 permit tcp any any eq 8088
+
+ip access-list extended ACL-FWAAS-d2f5d6a4-e48b-4426-8cdd-2654d2767721
+ 1 permit tcp any any established
+ 2 permit icmp any any echo-reply
+ 3 permit icmp any any unreachable
+ 4 permit icmp any any time-exceeded
+ 5 permit icmp any any timestamp-reply
+ 10 permit ip any any
+
vrf definition b9fa630ab5d143e6bbcad61f2d92c82c
 description Router b9fa630a-b5d1-43e6-bbca-d61f2d92c82c
 rd 65148:18687
 !
 interface BD-VIF5448
  description 6051ee46-9c18-4bdc-a168-a746ae0c69f6
  mac-address fa16.3e36.d649
  mtu 8950
  vrf forwarding 6051ee469c184bdca168a746ae0c69f6
  ip address 10.180.11.1 255.255.255.0
  ip nat stick
+ ip access-group ACL-FWAAS-d2f5d6a4-e48b-4426-8cdd-2654d2767721 out
+ ip access-group ACL-FWAAS-def33d0c-8831-46fa-b54c-f293b626a143 in
  ip policy route-map pbr-6051ee469c184bdca168a746ae0c69f6
  ntp disable
 !
 interface BD-VIF6443
  description 6051ee46-9c18-4bdc-a168-a746ae0c69f6
  mac-address fa16.3e72.9c4f
  mtu 8950
  vrf forwarding 6051ee469c184bdca168a746ae0c69f6
  ip address 10.237.208.16 255.255.255.0
  ip nat outside
  ip access-group EXT-TOS out
  ip policy route-map EXT-TOS
  ntp disable
 !
 interface BD-VIF6771
  description 6051ee46-9c18-4bdc-a168-a746ae0c69f6
  mac-address fa16.3e11.4e34
  mtu 8950
  vrf forwarding 6051ee469c184bdca168a746ae0c69f6
  ip address 10.180.12.1 255.255.255.0
  ip nat stick
+ ip access-group ACL-ACL-FWAAS-d2f5d6a4-e48b-4426-8cdd-2654d2767721 out
+ ip access-group ACL-FWAAS-def33d0c-8831-46fa-b54c-f293b626a143 in
  ip policy route-map pbr-6051ee469c184bdca168a746ae0c69f6
  ntp disable
 !
 ip nat inside source static 10.180.12.21 10.237.208.21 vrf 6051ee469c184bdca168a746ae0c69f6 redundancy 1 mapping-id 578507548 match-in-vrf
 ip nat inside source static 10.180.11.5 10.237.208.26 vrf 6051ee469c184bdca168a746ae0c69f6 redundancy 1 mapping-id 129381974 match-in-vrf
 ip nat inside source list NAT-6051ee469c184bdca168a746ae0c69f6 interface BD-VIF6443 vrf 6051ee469c184bdca168a746ae0c69f6 overload
 !
 ip route vrf 6051ee469c184bdca168a746ae0c69f6 0.0.0.0 0.0.0.0 10.237.208.1
```

As customers expect statefull behavior we prepend every customer ACL with entries that mimic statefulness. Hence we allow all established connections and ICMP packets that would otherwise require a state to be kept. As we map OpenStack firewall policy objects to an IOS ACL, we would like to be able to use the same ACL in a class-map for _ZBF_ as well.

```c
 1 permit tcp any any established
 2 permit icmp any any echo-reply
 3 permit icmp any any unreachable
 4 permit icmp any any time-exceeded
 5 permit icmp any any timestamp-reply
```

## Firewall policies between internal and external interfaces

Between internal and external interfaces statefull firewalling should be used. We implement this using the _zone-based firewall_ (ZBF) feature of IOS.

In below diff we show the change to a virtual router that is made after an ingress and egress OpenStack firewall policy  is bound to the external (nat outside) interface.

```diff
+zone security default
+!
+parameter-map type inspect-global
+ log dropped-packets
+ icmp-unreachable-allow
+  no application-inspect all
+ inspect vrf b9fa630ab5d143e6bbcad61f2d92c82c PAM-FWAAS-POLICE-VRF
+! 
+parameter-map type inspect-vrf PAM-FWAAS-POLICE-VRF
+ session total 1000000  
+ tcp syn-flood limit 2000
+!
+!
+ip access-list extended FWAAS-ACL-def33d0c-8831-46fa-b54c-f293b626a143
+ 1 permit tcp any any established
+ 2 permit icmp any any echo-reply
+ 3 permit icmp any any unreachable
+ 4 permit icmp any any time-exceeded
+ 5 permit icmp any any timestamp-reply
+ 10 permit tcp any any eq www
+ 20 permit udp any any eq domain
+ 30 permit icmp any any echo
+ 40 permit tcp any any eq 8088
+!
+ip access-list extended ACL-FWAAS-d2f5d6a4-e48b-4426-8cdd-2654d2767721
+ 1 permit tcp any any established
+ 2 permit icmp any any echo-reply
+ 3 permit icmp any any unreachable
+ 4 permit icmp any any time-exceeded
+ 5 permit icmp any any timestamp-reply
+ 10 permit ip any any
+!
+class-map type inspect match-all CM-FWAAS-def33d0c-8831-46fa-b54c-f293b626a143
+ match access-group name ACL-FWAAS-def33d0c-8831-46fa-b54c-f293b626a143
+class-map type inspect match-all CM-FWAAS-d2f5d6a4-e48b-4426-8cdd-2654d2767721
+ match access-group name ACL-FWAAS-d2f5d6a4-e48b-4426-8cdd-2654d2767721
+!
+ip access-list extended ACL-FWAAS-ALL
+ 10 permit ip any any
+!
+class-map type inspect match-all CM-FWAAS-ALL
+ match access-group name ACL-FWAAS-ALL
+!
+policy-map type inspect SP-FWAAS-ALLOW-INSPECT
+ class type inspect CM-FWAAS-ALL
+  inspect
+!
+policy-map type inspect PM-FWAAS-def33d0c-8831-46fa-b54c-f293b626a143
+ class type inspect CM-D072002-def33d0c-8831-46fa-b54c-f293b626a143
+  inspect
+ class class-default
+  drop log
+!
+policy-map type inspect PM-FWAAS-d2f5d6a4-e48b-4426-8cdd-2654d2767721
+ class type inspect CM-D072002-d2f5d6a4-e48b-4426-8cdd-2654d2767721
+  inspect
+ class class-default
+  drop log
+!
+zone security ZN-FWAAS-EXT-b9fa630ab5d143e6bbcad61f2d92c82c
+!
+zone-pair security ZP-FWAAS-IN2OUT-b9fa630ab5d143e6bbcad61f2d92c82c source default destination ZN-FWAAS-EXT-b9fa630ab5d143e6bbcad61f2d92c82c
+ service-policy type inspect PM-FWAAS-d2f5d6a4-e48b-4426-8cdd-2654d2767721
+!
+zone-pair security ZP-FWAAS-OUT2IN-b9fa630ab5d143e6bbcad61f2d92c82c source ZN-FWAAS-EXT-b9fa630ab5d143e6bbcad61f2d92c82c destination default
+ service-policy type inspect PM-FWAAS-def33d0c-8831-46fa-b54c-f293b626a143
+!
 vrf definition b9fa630ab5d143e6bbcad61f2d92c82c
  description Router b9fa630a-b5d1-43e6-bbca-d61f2d92c82c
  rd 65148:18687
 !
 interface BD-VIF5448
  description 6051ee46-9c18-4bdc-a168-a746ae0c69f6
  mac-address fa16.3e36.d649
  mtu 8950
  vrf forwarding 6051ee469c184bdca168a746ae0c69f6
+ redundancy rii 5448
+ redundancy group 1 decrement 1
  ip address 10.180.11.1 255.255.255.0
  ip nat stick
  ip policy route-map pbr-6051ee469c184bdca168a746ae0c69f6
  ntp disable
 !
 interface BD-VIF6443
  description 6051ee46-9c18-4bdc-a168-a746ae0c69f6
  mac-address fa16.3e72.9c4f
  mtu 8950
  vrf forwarding 6051ee469c184bdca168a746ae0c69f6
+ redundancy rii 6443
+ redundancy group 1 decrement 1
  ip address 10.237.208.16 255.255.255.0
  ip nat outside
  ip access-group EXT-TOS out
+ zone-member security ZN-FWAAS-EXT-b9fa630ab5d143e6bbcad61f2d92c82c
  ip policy route-map EXT-TOS
  ntp disable
 !
 interface BD-VIF6771
  description 6051ee46-9c18-4bdc-a168-a746ae0c69f6
  mac-address fa16.3e11.4e34
  mtu 8950
  vrf forwarding 6051ee469c184bdca168a746ae0c69f6
+ redundancy rii 6771
+ redundancy group 1 decrement 1
  ip address 10.180.12.1 255.255.255.0
  ip nat stick
  ip policy route-map pbr-6051ee469c184bdca168a746ae0c69f6
  ntp disable
 !
 ip nat inside source static 10.180.12.21 10.237.208.21 vrf 6051ee469c184bdca168a746ae0c69f6 redundancy 1 mapping-id 578507548 match-in-vrf
 ip nat inside source static 10.180.11.5 10.237.208.26 vrf 6051ee469c184bdca168a746ae0c69f6 redundancy 1 mapping-id 129381974 match-in-vrf
 ip nat inside source list NAT-6051ee469c184bdca168a746ae0c69f6 interface BD-VIF6443 vrf 6051ee469c184bdca168a746ae0c69f6 overload
 !
 ip route vrf 6051ee469c184bdca168a746ae0c69f6 0.0.0.0 0.0.0.0 10.237.208.1
```
We use the parameter maps to disable L7 firewalling and limit the sessions per VRF as well as apply SYN cookie protections.

As ACLs can also be used in the stateless manner, we prepend the stateful mimicing to every ACL, even when used for _ZBF_, followed by the actual rules beginning in sequence 10. Every ACL is then simply linked to a _class-map_ which is then linked to a _service-policy_.

We decided to create a single zone that will only be assigned to the outside interface, all other interfaces reside in the default zone. That allows us to support traffic that is coming into the device via an MPLS link without adding an explicit _zone-pair_ relationship with this MPLS interface. We create _zone-pair_ relationships from the default zone (inside) to the created zone (external) and vice versa and apply the respective service policies on it.

In order to replicate sessions to the standby device, we apply an _redundant interface identifier_ (RII) on every interface and assign it to redundancy group 1. We do not want a decrement of priority on interface failure here, yet the CLI does not accept the command if we do not supply this.

## Relation between configuration objects
### _access-lists_
We will map an OpenStack firewall policy to an ACL, as firewall policies can be bound on multiple interfaces, so we expect from ACLs. That means, an ACL will be bound as _access-group_ to multiple ports, but at the same time it will also be bound to a _class-map_. ACLs are also expected to change and any change should be reflected within _ZBF_ or simple _access-group_ filtering.

### _class-maps_ and _service-policy_
In the current config draft, these objects are only needed to link an ACL to the _ZBF_ inspect feature. For every ACL there can be 0 to 1 _class-maps_, and for every _class-map_ there is always exactly 1 _service-policy_. On the turn side, a single service policy can be mapped to an arbitrary number of _zone-pairs_ which will all reside in different VRFs. These objects are likely not to be changed during their lifetime.

### _zone_ and _zone-pair_
For every VRF there can be at most 1 zone, and either 0 or 2 _zone-pairs_. We limit the number of VRFs at 500 per hardware device. These objects are likely not to be changed during their lifetime.
