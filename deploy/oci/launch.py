"""Chapter 15: launch the Always Free Ampere A1 instance.

    uv run deploy/oci/launch.py plan
    uv run deploy/oci/launch.py apply
    uv run deploy/oci/launch.py status

Frankfurt's free A1 capacity is one of the most contested in Oracle's
fleet, so `apply` tries every availability domain in the region in
turn and reports which one worked, rather than failing on the first
"Out of host capacity".

The shape here (2 OCPU, 12 GB) is inside the Always Free limit: up to
4 OCPU and 24 GB of A1 total, spread across up to four instances.
Nothing here is billable while it stays under that ceiling.
"""

import sys
import time

import oci

INSTANCE_NAME = "voice-agents-sip"
SHAPE = "VM.Standard.A1.Flex"
OCPUS = 2
MEMORY_GB = 12
IMAGE_NAME_PREFIX = "Canonical-Ubuntu-24.04-aarch64"
SSH_PUBLIC_KEY_PATH = "~/.ssh/voice_agents_oci.pub"

CLOUD_INIT = """#cloud-config
package_update: true
packages:
  - docker.io
  - docker-compose-v2
runcmd:
  - systemctl enable --now docker
  - usermod -aG docker ubuntu
"""


def clients():
    config = oci.config.from_file("~/.oci/config")
    compute = oci.core.ComputeClient(config)
    net = oci.core.VirtualNetworkClient(config)
    identity = oci.identity.IdentityClient(config)
    return config, compute, net, identity


def find_subnet(config, net):
    from provision import SUBNET_NAME, VCN_NAME  # noqa: E402
    tenancy = config["tenancy"]
    vcn = next((v for v in net.list_vcns(tenancy).data
               if v.display_name == VCN_NAME), None)
    if vcn is None:
        raise SystemExit("Run provision.py apply first: no VCN yet.")
    subnet = next((s for s in net.list_subnets(tenancy, vcn_id=vcn.id).data
                   if s.display_name == SUBNET_NAME), None)
    if subnet is None:
        raise SystemExit("Run provision.py apply first: no subnet yet.")
    return subnet


def find_image(config, compute):
    tenancy = config["tenancy"]
    images = compute.list_images(
        tenancy, operating_system="Canonical Ubuntu", shape=SHAPE,
    ).data
    matches = sorted(
        (i for i in images if i.display_name.startswith(IMAGE_NAME_PREFIX)),
        key=lambda i: i.time_created, reverse=True,
    )
    if not matches:
        raise SystemExit(f"No image found matching {IMAGE_NAME_PREFIX}")
    return matches[0]


def plan(config, compute, net, identity) -> None:
    subnet = find_subnet(config, net)
    image = find_image(config, compute)
    ads = identity.list_availability_domains(config["tenancy"]).data
    print(f"Instance:  {INSTANCE_NAME}")
    print(f"Shape:     {SHAPE}, {OCPUS} OCPU, {MEMORY_GB} GB "
          f"(within the Always Free 4 OCPU / 24 GB A1 ceiling)")
    print(f"Image:     {image.display_name}")
    print(f"Subnet:    {subnet.display_name} ({subnet.cidr_block})")
    print(f"Will try:  {', '.join(ad.name for ad in ads)}")
    print("Public IP: an ephemeral Always Free address, assigned on "
          "create")
    print("SSH key:   from", SSH_PUBLIC_KEY_PATH)
    print("\nNothing has been created. Run with 'apply' to create it.")


def apply(config, compute, net, identity) -> None:
    import os

    subnet = find_subnet(config, net)
    image = find_image(config, compute)
    ads = identity.list_availability_domains(config["tenancy"]).data

    key_path = os.path.expanduser(SSH_PUBLIC_KEY_PATH)
    if not os.path.exists(key_path):
        raise SystemExit(f"No SSH key at {key_path}. Generate one first.")
    ssh_key = open(key_path).read().strip()

    existing = [i for i in compute.list_instances(config["tenancy"]).data
               if i.display_name == INSTANCE_NAME
               and i.lifecycle_state not in ("TERMINATED", "TERMINATING")]
    if existing:
        print(f"{INSTANCE_NAME} already exists "
              f"({existing[0].lifecycle_state}). Nothing to do.")
        return

    last_error = None
    for ad in ads:
        print(f"Trying {ad.name}...")
        try:
            instance = compute.launch_instance(
                oci.core.models.LaunchInstanceDetails(
                    compartment_id=config["tenancy"],
                    availability_domain=ad.name,
                    shape=SHAPE,
                    shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                        ocpus=OCPUS, memory_in_gbs=MEMORY_GB,
                    ),
                    display_name=INSTANCE_NAME,
                    create_vnic_details=oci.core.models.CreateVnicDetails(
                        subnet_id=subnet.id, assign_public_ip=True,
                    ),
                    source_details=oci.core.models.InstanceSourceViaImageDetails(
                        image_id=image.id,
                    ),
                    metadata={
                        "ssh_authorized_keys": ssh_key,
                        "user_data": __import__("base64").b64encode(
                            CLOUD_INIT.encode()).decode(),
                    },
                )
            ).data
        except oci.exceptions.ServiceError as e:
            last_error = e
            print(f"  {ad.name}: {e.message}")
            if "capacity" not in e.message.lower():
                raise
            time.sleep(2)
            continue

        print(f"Launched in {ad.name}, waiting for it to run...")
        instance = oci.wait_until(
            compute, compute.get_instance(instance.id),
            "lifecycle_state", "RUNNING", max_wait_seconds=300,
        ).data
        vnics = compute.list_vnic_attachments(
            config["tenancy"], instance_id=instance.id).data
        vnic = net.get_vnic(vnics[0].vnic_id).data
        print(f"\nRunning. Public IP: {vnic.public_ip}")
        print(f"SSH:  ssh -i ~/.ssh/voice_agents_oci ubuntu@{vnic.public_ip}")
        print("\nCloud-init is installing Docker; give it a minute before "
              "connecting.")
        return

    raise SystemExit(
        f"Every availability domain reported capacity issues. "
        f"Last error: {last_error}"
    )


def status(config, compute, net, identity) -> None:
    instances = [i for i in compute.list_instances(config["tenancy"]).data
                if i.display_name == INSTANCE_NAME]
    if not instances:
        print("No instance found.")
        return
    for i in instances:
        print(f"{i.display_name}: {i.lifecycle_state}  "
              f"({i.availability_domain}, {i.shape})")
        if i.lifecycle_state == "RUNNING":
            vnics = compute.list_vnic_attachments(
                config["tenancy"], instance_id=i.id).data
            if vnics:
                vnic = net.get_vnic(vnics[0].vnic_id).data
                print(f"  public ip: {vnic.public_ip}")


if __name__ == "__main__":
    sys.path.insert(0, ".")
    config, compute, net, identity = clients()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":
        plan(config, compute, net, identity)
    elif cmd == "apply":
        apply(config, compute, net, identity)
    elif cmd == "status":
        status(config, compute, net, identity)
    else:
        raise SystemExit(__doc__.splitlines()[2].strip())
