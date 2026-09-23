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

# SIP signalling: Twilio's documented signalling edges, one /30
# each. Source: twilio.com/docs/sip-trunking/ip-addresses, fetched
# 2026-09-23. Keep this list identical to TWILIO_SIP_CIDRS in
# provision.py; the two firewalls should always agree.
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

# RTP media: a single global block, separate from the signalling
# edges above. Same source and date. Keep this identical to
# TWILIO_RTP_CIDR in provision.py.
TWILIO_RTP_CIDR="168.86.128.0/18"
open_range_from udp 10000 10020 "$TWILIO_RTP_CIDR"

sudo netfilter-persistent save
echo "Rules applied and saved."
sudo iptables -L INPUT -n --line-numbers
