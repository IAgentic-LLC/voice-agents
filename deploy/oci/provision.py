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

# Every carrier publishes its own signalling and media addresses so
# a trunk can be firewalled to them instead of the world, and no two
# carriers shape that list the same way. This server accepts SIP
# from whichever of these are configured; adding a second carrier
# (Chapter 16) means adding its ranges here, not changing anything
# else in this file.
PROVIDERS = {
    # Source: twilio.com/docs/sip-trunking/ip-addresses, fetched
    # 2026-09-23. Frankfurt is the edge this instance actually
    # needs; the rest are kept in case Twilio routes a call through
    # a different one. Media is one global block, separate from the
    # per-region signalling addresses.
    "twilio": {
        "sip_cidrs": [
            "35.156.191.128/30",  # Frankfurt, the edge this faces
            "54.172.60.0/30",     # Virginia
            "54.244.51.0/30",     # Oregon
            "54.171.127.192/30",  # Ireland
            "54.65.63.192/30",    # Tokyo
            "54.169.127.128/30",  # Singapore
            "54.252.254.64/30",   # Sydney
            "177.71.206.192/30",  # Sao Paulo
        ],
        "rtp_cidrs": ["168.86.128.0/18"],
    },
    # Source: sip.telnyx.com, fetched 2026-09-23. Signalling is two
    # single addresses per region rather than Twilio's /30 blocks.
    # Media is fourteen separate CIDRs over a much wider port range
    # (RTP_RANGE below is this server's own local range, unaffected
    # by that; only the source addresses differ per carrier).
    "telnyx": {
        "sip_cidrs": [
            "185.246.41.140/32",  # Europe, the edge this faces
            "185.246.41.141/32",  # Europe
            "192.76.120.10/32",   # US
            "64.16.250.10/32",    # US
            "192.76.120.31/32",   # Canada
            "64.16.250.13/32",    # Canada
            "103.115.244.145/32",  # Australia
            "103.115.244.146/32",  # Australia
            "185.246.42.128/32",  # Middle East
            "185.246.42.129/32",  # Middle East
            "103.115.244.158/32",  # Asia (beta)
            "103.115.244.159/32",  # Asia (beta)
        ],
        "rtp_cidrs": [
            "36.255.198.128/25", "50.114.136.128/25", "50.114.144.0/21",
            "64.16.226.0/24", "64.16.227.0/24", "64.16.228.0/24",
            "64.16.229.0/24", "64.16.230.0/24", "64.16.248.0/24",
            "64.16.249.0/24", "103.115.244.128/25", "103.115.247.0/24",
            "185.246.41.128/25", "185.246.42.128/28",
        ],
    },
}

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
    for name, ranges in PROVIDERS.items():
        print(f"Open to {name.title()}'s SIP ranges only "
              f"({len(ranges['sip_cidrs'])} CIDRs):")
        for proto, port, why in SIP_RULES:
            print(f"  {'tcp' if proto == 6 else 'udp':<4} {port:<6}{why}")
        n = len(ranges["rtp_cidrs"])
        print(f"Open to {name.title()}'s media range"
              f"{'s' if n != 1 else ''} only ({n} "
              f"CIDR{'s' if n != 1 else ''}):")
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
    for name, ranges in PROVIDERS.items():
        for cidr in ranges["sip_cidrs"]:
            for proto, port, why in SIP_RULES:
                ingress.append(oci.core.models.IngressSecurityRule(
                    protocol=str(proto), source=cidr,
                    source_type="CIDR_BLOCK",
                    description=f"{why} ({name.title()})",
                    tcp_options=(oci.core.models.TcpOptions(
                        destination_port_range=oci.core.models.PortRange(
                            min=port, max=port))
                        if proto == 6 else None),
                    udp_options=(oci.core.models.UdpOptions(
                        destination_port_range=oci.core.models.PortRange(
                            min=port, max=port))
                        if proto == 17 else None),
                ))
        # RTP arrives from each carrier's own media block, not its
        # signalling addresses, so these rules are scoped to
        # rtp_cidrs on their own rather than repeated per SIP CIDR.
        for cidr in ranges["rtp_cidrs"]:
            ingress.append(oci.core.models.IngressSecurityRule(
                protocol="17", source=cidr, source_type="CIDR_BLOCK",
                description=f"RTP media ({name.title()})",
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
    carriers = ", ".join(name.title() for name in PROVIDERS)
    print(f"Security list updated: {len(ingress)} ingress rules "
          f"({len(RULES)} open).")
    print(f"The rest are scoped to a carrier: {carriers}.")

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
