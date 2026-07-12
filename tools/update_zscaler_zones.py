#!/usr/bin/env python3
"""Refresh the ZSCALER_ZEN zone in the egress policies from Zscaler's
published enforcement-node ranges (config.zscaler.com JSON feed).

Zscaler expands these ranges over time; a firewall that was proven open last
quarter can silently miss a new range. The zscaler-refresh workflow runs this
weekly and opens a PR when the feed changes — the RuleHawk gate on that PR
then PROVES whether the current firewall configs already permit the new
ranges (connectivity-ok) or need a change first (connectivity-broken).

Stdlib only; fails loudly and touches nothing on any fetch/parse error.
"""

import ipaddress
import json
import sys
import urllib.request

FEED = "https://config.zscaler.com/api/zscaler.net/hubs/cidr/json/recommended"
POLICIES = ["policy/egress-edge.json", "policy/egress-host.json"]


def fetch_ranges():
    with urllib.request.urlopen(FEED, timeout=30) as r:
        data = json.load(r)
    prefixes = data.get("hubPrefixes")
    if not prefixes or not isinstance(prefixes, list):
        raise SystemExit(f"unexpected feed shape from {FEED}: {list(data)[:5]}")
    out = []
    for p in prefixes:
        ipaddress.ip_network(p)          # validate; raises on garbage
        out.append(p)
    return sorted(out)


def main():
    ranges = fetch_ranges()
    changed = False
    for path in POLICIES:
        with open(path, encoding="utf-8") as fh:
            pol = json.load(fh)
        if pol["zones"].get("ZSCALER_ZEN") == ranges:
            continue
        pol["zones"]["ZSCALER_ZEN"] = ranges
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(pol, fh, indent=2)
            fh.write("\n")
        changed = True
        print(f"updated {path}: ZSCALER_ZEN -> {len(ranges)} range(s)")
    if not changed:
        print("ZEN ranges unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
