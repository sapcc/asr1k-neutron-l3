

VRF_CLI_INIT = """vrf definition {name}
    description {description}
    rd {rd}
    address-family ipv4
        export map exp-{name}"""

BDI_NO_POLICY_CLI_INIT = """interface BDI{id}
    description {description}
    mac-address {mac}
    mtu {mtu}
    vrf forwarding {vrf}
    ip address {ip} {netmask}
    ip nat {nat}
    no shutdown"""

BDI_POLICY_CLI_INIT = """interface BDI{id}
    description {description}
    mac-address {mac}
    mtu {mtu}
    vrf forwarding {vrf}
    ip address {ip} {netmask}
    ip nat {nat}
    ip policy route-map {route_map}
    no shutdown"""


PBR_ROUTE_MAP = """route-map pbr-{vrf} permit 10 
    match ip address PBR-{vrf}
    set ip next-hop {gateway} force"""

PBR_ACCESS_LIST = """ip access-list extended PBR-{vrf}
    permit ip any {network} {netmask}"""
