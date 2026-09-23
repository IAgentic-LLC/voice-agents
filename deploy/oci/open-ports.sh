#!/bin/bash
# Chapter 15: Oracle's VCN security list is not enough on its own.
# Ubuntu images on OCI ship their own iptables rules, pre-populated
# with a REJECT catch-all after SSH, and that firewall does not know
# what the security list allows. Both have to open the same ports, or
# a packet the security list lets through is dropped here instead.
#
# The first version of this script opened SIP and RTP to 0.0.0.0/0 at
# this layer while the security list restricted them to Twilio's
# ranges, which meant only one of the two firewalls was actually
# doing that job. If the security list were ever loosened by mistake,
# this one would not have caught it. So SIP and RTP are scoped here
# too, from the same list the security list uses.
set -euo pipefail

open_world() {
  local proto=$1 port=$2
  sudo iptables -C INPUT -p "$proto" --dport "$port" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 5 -p "$proto" --dport "$port" -j ACCEPT
}

open_from() {
  local proto=$1 port=$2 src=$3
  sudo iptables -C INPUT -p "$proto" -s "$src" --dport "$port" -j ACCEPT \
    2>/dev/null \
    || sudo iptables -I INPUT 5 -p "$proto" -s "$src" --dport "$port" \
         -j ACCEPT
}

open_range_from() {
  local proto=$1 lo=$2 hi=$3 src=$4
  sudo iptables -C INPUT -p "$proto" -s "$src" --dport "$lo:$hi" -j ACCEPT \
    2>/dev/null \
    || sudo iptables -I INPUT 5 -p "$proto" -s "$src" --dport "$lo:$hi" \
         -j ACCEPT
}

# LiveKit itself: no reason a browser or an agent worker would only
# ever call from Twilio, so these stay open.
open_world tcp 7880
open_world tcp 7881
open_world udp 7882

# SIP signalling and RTP media, one carrier at a time. Keep this
# identical to PROVIDERS in provision.py; the two firewalls should
# always agree, on every carrier, not just the first one.

# Twilio. Source: twilio.com/docs/sip-trunking/ip-addresses, fetched
# 2026-09-23.
TWILIO_SIP_CIDRS=(
  "35.156.191.128/30"  # Frankfurt, the edge this instance faces
  "54.172.60.0/30"     # Virginia
  "54.244.51.0/30"     # Oregon
  "54.171.127.192/30"  # Ireland
  "54.65.63.192/30"    # Tokyo
  "54.169.127.128/30"  # Singapore
  "54.252.254.64/30"   # Sydney
  "177.71.206.192/30"  # Sao Paulo
)
for cidr in "${TWILIO_SIP_CIDRS[@]}"; do
  open_from tcp 5060 "$cidr"
  open_from udp 5060 "$cidr"
done
open_range_from udp 10000 10020 "168.86.128.0/18"

# Telnyx. Source: sip.telnyx.com, fetched 2026-09-23. Two single
# addresses per region, not /30 blocks, and media is fourteen
# separate CIDRs rather than Twilio's one.
TELNYX_SIP_CIDRS=(
  "185.246.41.140/32"   # Europe, the edge this instance faces
  "185.246.41.141/32"   # Europe
  "192.76.120.10/32"    # US
  "64.16.250.10/32"     # US
  "192.76.120.31/32"    # Canada
  "64.16.250.13/32"     # Canada
  "103.115.244.145/32"  # Australia
  "103.115.244.146/32"  # Australia
  "185.246.42.128/32"   # Middle East
  "185.246.42.129/32"   # Middle East
  "103.115.244.158/32"  # Asia (beta)
  "103.115.244.159/32"  # Asia (beta)
)
for cidr in "${TELNYX_SIP_CIDRS[@]}"; do
  open_from tcp 5060 "$cidr"
  open_from udp 5060 "$cidr"
done
TELNYX_RTP_CIDRS=(
  "36.255.198.128/25" "50.114.136.128/25" "50.114.144.0/21"
  "64.16.226.0/24" "64.16.227.0/24" "64.16.228.0/24"
  "64.16.229.0/24" "64.16.230.0/24" "64.16.248.0/24"
  "64.16.249.0/24" "103.115.244.128/25" "103.115.247.0/24"
  "185.246.41.128/25" "185.246.42.128/28"
)
for cidr in "${TELNYX_RTP_CIDRS[@]}"; do
  open_range_from udp 10000 10020 "$cidr"
done

sudo netfilter-persistent save
echo "Rules applied and saved."
sudo iptables -L INPUT -n --line-numbers
