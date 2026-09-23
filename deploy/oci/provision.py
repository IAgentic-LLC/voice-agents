"""Chapter 15: stand up the network and firewall for a real phone number.

    uv run deploy/oci/provision.py plan
    uv run deploy/oci/provision.py apply
    uv run deploy/oci/provision.py status

Everything Chapter 14 ran in Docker on one laptop needs a public
address before a carrier can reach it. This script builds the network
a self-hosted LiveKit SIP stack needs on Oracle's Always Free tier:
a VCN, one public subnet, an internet gateway, and a security list
that opens exactly the ports SIP telephony needs and nothing else.

It does not create the compute instance. That step costs a public
IPv4 and, on a busy region, may need retrying across availability
domains, so it is a separate script (launch.py) with its own
confirmation.

`plan` prints what would be created without creating anything.
`apply` creates it, and is safe to run twice: it checks for an
existing resource with the same display name first.
"""

import sys

import oci

REGION = "eu-frankfurt-1"
VCN_NAME = "voice-agents-sip"
VCN_CIDR = "10.20.0.0/16"
SUBNET_NAME = "voice-agents-sip-public"
SUBNET_CIDR = "10.20.1.0/24"

# Twilio's documented SIP signalling ranges, one /30 per edge
# location. Real carriers publish these so a trunk can be firewalled
# to them instead of the world. Source: twilio.com/docs/sip-trunking/
# ip-addresses, fetched 2026-09-23. Frankfurt is the one this
# instance actually needs; the others are kept in case Twilio routes
# a call through a different edge.
TWILIO_SIP_CIDRS = [
    "35.156.191.128/30",  # Frankfurt, the edge this instance faces
    "54.172.60.0/30",     # Virginia
    "54.244.51.0/30",     # Oregon
    "54.171.127.192/30",  # Ireland
    "54.65.63.192/30",    # Tokyo
    "54.169.127.128/30",  # Singapore
    "54.252.254.64/30",   # Sydney
    "177.71.206.192/30",  # Sao Paulo
]

# Twilio's media (RTP) gateways are a single global block, separate
# from the per-region signalling addresses above: signalling and
# media do not come from the same IPs. Same source and date.
TWILIO_RTP_CIDR = "168.86.128.0/18"

# Ports this stack needs, and why. Anything not listed stays closed.
RULES = [
    (6, 22, "SSH, for setup and maintenance"),
    (6, 7880, "LiveKit server: HTTP/WebSocket signalling"),
    (6, 7881, "LiveKit server: ICE/TCP fallback"),
    (17, 7882, "LiveKit server: ICE/UDP media"),
]
SIP_RULES = [
    (6, 5060, "SIP signalling (TCP)"),
    (17, 5060, "SIP signalling (UDP)"),
]
RTP_RANGE = (10000, 10020)  # UDP media for SIP calls


def client():
    config = oci.config.from_file("~/.oci/config")
    return config, oci.core.VirtualNetworkClient(config)


def find_by_name(items, name):
    return next((i for i in items if i.display_name == name), None)


def plan(config, net) -> None:
    print(f"Region:          {REGION}")
    print(f"VCN:             {VCN_NAME}  {VCN_CIDR}")
    print(f"Subnet:          {SUBNET_NAME}  {SUBNET_CIDR}  (public)")
    print("Open to the world:")
    for proto, port, why in RULES:
        print(f"  {'tcp' if proto == 6 else 'udp':<4} {port:<6}{why}")
    print(f"Open to Twilio's SIP ranges only ({len(TWILIO_SIP_CIDRS)} "
          f"CIDRs):")
    for proto, port, why in SIP_RULES:
        print(f"  {'tcp' if proto == 6 else 'udp':<4} {port:<6}{why}")
    print(f"Open to Twilio's media range only ({TWILIO_RTP_CIDR}):")
    print(f"  udp  {RTP_RANGE[0]}-{RTP_RANGE[1]:<6}RTP media for calls")
    print("\nNothing has been created. Run with 'apply' to create it.")


def apply(config, net) -> str:
    tenancy = config["tenancy"]

    vcn = find_by_name(net.list_vcns(tenancy).data, VCN_NAME)
    if vcn is None:
        print(f"Creating VCN {VCN_NAME} ({VCN_CIDR})...")
        vcn = net.create_vcn(oci.core.models.CreateVcnDetails(
            compartment_id=tenancy, cidr_block=VCN_CIDR,
            display_name=VCN_NAME,
        )).data
        vcn = oci.wait_until(
            net, net.get_vcn(vcn.id), "lifecycle_state", "AVAILABLE"
        ).data
    else:
        print(f"VCN {VCN_NAME} already exists.")

    igws = net.list_internet_gateways(tenancy, vcn_id=vcn.id).data
    igw = find_by_name(igws, f"{VCN_NAME}-igw")
    if igw is None:
        print("Creating internet gateway...")
        igw = net.create_internet_gateway(
            oci.core.models.CreateInternetGatewayDetails(
                compartment_id=tenancy, vcn_id=vcn.id, is_enabled=True,
                display_name=f"{VCN_NAME}-igw",
            )
        ).data
        igw = oci.wait_until(
            net, net.get_internet_gateway(igw.id),
            "lifecycle_state", "AVAILABLE",
        ).data
    else:
        print("Internet gateway already exists.")

    rts = net.list_route_tables(tenancy, vcn_id=vcn.id).data
    default_rt = rts[0]
    net.update_route_table(
        default_rt.id,
        oci.core.models.UpdateRouteTableDetails(route_rules=[
            oci.core.models.RouteRule(
                destination="0.0.0.0/0",
                destination_type="CIDR_BLOCK",
                network_entity_id=igw.id,
            )
        ]),
    )
    print("Default route table points at the internet gateway.")

    ingress = []
    for proto, port, why in RULES:
        ingress.append(oci.core.models.IngressSecurityRule(
            protocol=str(proto), source="0.0.0.0/0",
            source_type="CIDR_BLOCK", description=why,
            tcp_options=(oci.core.models.TcpOptions(
                destination_port_range=oci.core.models.PortRange(
                    min=port, max=port))
                if proto == 6 else None),
            udp_options=(oci.core.models.UdpOptions(
                destination_port_range=oci.core.models.PortRange(
                    min=port, max=port))
                if proto == 17 else None),
        ))
    for cidr in TWILIO_SIP_CIDRS:
        for proto, port, why in SIP_RULES:
            ingress.append(oci.core.models.IngressSecurityRule(
                protocol=str(proto), source=cidr,
                source_type="CIDR_BLOCK", description=f"{why} (Twilio)",
                tcp_options=(oci.core.models.TcpOptions(
                    destination_port_range=oci.core.models.PortRange(
                        min=port, max=port))
                    if proto == 6 else None),
                udp_options=(oci.core.models.UdpOptions(
                    destination_port_range=oci.core.models.PortRange(
                        min=port, max=port))
                    if proto == 17 else None),
            ))
    # RTP arrives from Twilio's media block, not its signalling
    # addresses, so this rule is scoped to TWILIO_RTP_CIDR on its
    # own rather than repeated once per signalling CIDR above.
    ingress.append(oci.core.models.IngressSecurityRule(
        protocol="17", source=TWILIO_RTP_CIDR, source_type="CIDR_BLOCK",
        description="RTP media (Twilio)",
        udp_options=oci.core.models.UdpOptions(
            destination_port_range=oci.core.models.PortRange(
                min=RTP_RANGE[0], max=RTP_RANGE[1])),
    ))

    sls = net.list_security_lists(tenancy, vcn_id=vcn.id).data
    default_sl = sls[0]
    net.update_security_list(
        default_sl.id,
        oci.core.models.UpdateSecurityListDetails(
            ingress_security_rules=ingress,
            egress_security_rules=[oci.core.models.EgressSecurityRule(
                protocol="all", destination="0.0.0.0/0",
                destination_type="CIDR_BLOCK",
            )],
        ),
    )
    print(f"Security list updated: {len(ingress)} ingress rules "
          f"({len(RULES)} open, the rest scoped to Twilio).")

    ads = oci.identity.IdentityClient(config).list_availability_domains(
        tenancy).data
    subnet = find_by_name(net.list_subnets(tenancy, vcn_id=vcn.id).data,
                          SUBNET_NAME)
    if subnet is None:
        print(f"Creating subnet {SUBNET_NAME} ({SUBNET_CIDR})...")
        subnet = net.create_subnet(oci.core.models.CreateSubnetDetails(
            compartment_id=tenancy, vcn_id=vcn.id, cidr_block=SUBNET_CIDR,
            display_name=SUBNET_NAME,
            route_table_id=default_rt.id, security_list_ids=[default_sl.id],
            prohibit_public_ip_on_vnic=False,
        )).data
        subnet = oci.wait_until(
            net, net.get_subnet(subnet.id), "lifecycle_state", "AVAILABLE"
        ).data
    else:
        print(f"Subnet {SUBNET_NAME} already exists.")

    print(f"\nDone. Subnet OCID: {subnet.id}")
    return subnet.id


def status(config, net) -> None:
    tenancy = config["tenancy"]
    vcn = find_by_name(net.list_vcns(tenancy).data, VCN_NAME)
    if vcn is None:
        print("Nothing created yet.")
        return
    print(f"VCN {vcn.display_name}: {vcn.lifecycle_state}")
    for s in net.list_subnets(tenancy, vcn_id=vcn.id).data:
        print(f"  subnet {s.display_name}: {s.lifecycle_state}  "
              f"{s.cidr_block}  id={s.id}")
    sl = net.list_security_lists(tenancy, vcn_id=vcn.id).data[0]
    print(f"  security list: {len(sl.ingress_security_rules)} "
          f"ingress rules")


if __name__ == "__main__":
    config, net = client()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":
        plan(config, net)
    elif cmd == "apply":
        apply(config, net)
    elif cmd == "status":
        status(config, net)
    else:
        raise SystemExit(__doc__.splitlines()[2].strip())
