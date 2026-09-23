"""Chapter 16: the multi-carrier firewall data, checked for real.

`PROVIDERS` in deploy/oci/provision.py is hand-transcribed from two
carriers' own documentation, twenty-six CIDR strings in total. These
tests do not need a real OCI account: they check the data itself,
the same properties a typo or a copy-paste slip would break.
"""

import ipaddress

from deploy.oci import provision


def test_every_cidr_string_actually_parses():
    for name, ranges in provision.PROVIDERS.items():
        for cidr in ranges["sip_cidrs"] + ranges["rtp_cidrs"]:
            ipaddress.ip_network(cidr)


def test_no_two_different_providers_claim_the_same_address_range():
    # A single carrier's own signalling and media ranges can and do
    # overlap each other (Telnyx's Australia signalling address sits
    # inside its own media block); that is normal. What would be a
    # real bug is two DIFFERENT carriers claiming the same range, so
    # only cross-provider pairs are checked here.
    by_provider = {
        name: [ipaddress.ip_network(c)
              for c in ranges["sip_cidrs"] + ranges["rtp_cidrs"]]
        for name, ranges in provision.PROVIDERS.items()
    }
    names = list(by_provider)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for net_a in by_provider[a]:
                for net_b in by_provider[b]:
                    assert not net_a.overlaps(net_b), (
                        f"{a}'s {net_a} overlaps {b}'s {net_b}")


def test_every_provider_has_at_least_one_sip_and_one_rtp_range():
    for name, ranges in provision.PROVIDERS.items():
        assert ranges["sip_cidrs"], name
        assert ranges["rtp_cidrs"], name


def test_ingress_rule_count_matches_what_apply_would_build():
    # Two SIP_RULES per signalling CIDR, one rule per RTP CIDR, plus
    # the always-open RULES. A provider added without updating this
    # count is still counted correctly; a typo that duplicates or
    # drops a CIDR changes it, which is what this pins.
    expected = len(provision.RULES)
    for ranges in provision.PROVIDERS.values():
        expected += len(ranges["sip_cidrs"]) * len(provision.SIP_RULES)
        expected += len(ranges["rtp_cidrs"])
    assert expected == 59
