# RuleHawk demo — firewall config-as-code, with proofs

[![Firewall gate](https://github.com/optimesh-ai/rulehawk-demo/actions/workflows/rulehawk.yml/badge.svg)](https://github.com/optimesh-ai/rulehawk-demo/actions/workflows/rulehawk.yml)

**Every firewall change in this repo is a pull request. Before it merges,
[RuleHawk](https://github.com/optimesh-ai/RuleHawk) proves three things — offline,
from the config files alone, in about a second:**

1. **Nothing dumb shipped** — dead, shadowed, and redundant rules are caught with
   exact proofs (and a copy-paste *Cleanup plan* for the safe deletions).
2. **PCI stays isolated** — the zone policy (`CORP must never reach PCI`, …) is
   re-proven on every diff. A violation is reported as a **concrete witness
   packet** you can verify by eye, annotated on the exact changed line.
3. **The Zscaler rollout keeps working** — `must_reach` assertions prove the
   egress firewalls actually permit the ZEN ranges, GRE and IPsec tunnel flows.
   A change that would break them goes red **before** it ships, not during the
   maintenance window.

No agents, no device credentials, no appliance. Configs never leave the runner.

---

## See it catch real mistakes (2 minutes)

**Ten pull requests are permanently open** in this repo — nine realistic bad
changes held red at the gate, and one clean change that sails through green.
Open any of them and look at the checks + the sticky review comment. They span
all six vendors and every finding class RuleHawk produces:

| # | PR | Vendor | What RuleHawk says |
|---|---|---|---|
| [1](../../pull/1) | "Temporarily" allow CORP → PCI on 445 | Cisco IOS | 🔴 **segmentation-violation** — witness `10.20.0.1 → 10.10.0.1:445`, paste-ready deny |
| [2](../../pull/2) | Remove the "unused" UDP 4500 permit | Cisco ASA | 🔴 **connectivity-broken** — IPsec NAT-T dies; 500 open ≠ proof for 4500 |
| [3](../../pull/3) | "Emergency block" added below the matching permit | Cisco IOS | 🔴 **intent-inversion-deny-dead** — "the traffic you meant to block is ALLOWED" |
| [4](../../pull/4) | Blanket `-j ACCEPT` on FORWARD "while debugging" | iptables | 🔴 **permit-any-any** + a batch of **segmentation-violations** |
| [5](../../pull/5) | RDP + SMB to the jump box from anywhere | Cisco IOS | 🔴 **dangerous-exposure** (RDP/SMB from `any` source) |
| [6](../../pull/6) | New app permit added below the catch-all deny | Cisco IOS | 🔴 **intent-inversion-permit-dead** — silent connectivity loss |
| [7](../../pull/7) | A guest-VLAN block that two earlier permits already defeat | Cisco NX-OS | 🔴 **union-shadowed-deny-dead** — cumulative shadow, cites the pair |
| [8](../../pull/8) | CORP reporting tool → PCI database | Palo Alto PAN-OS | 🔴 **segmentation-violation** — witness `10.20.0.1 → 10.10.20.1:5432` |
| [9](../../pull/9) | Zscaler adds a new ZEN range the firewall misses | policy | 🔴 **connectivity-broken** — egress readiness re-proven on every range change |
| [10](../../pull/10) | Least-privilege: drop an unused port | Juniper Junos | ✅ **all green** — isolation still proven, safe to merge |

Merges are blocked on the red ones; the sticky review comment carries the witness
packets; the Security tab gets SARIF annotations on the exact lines. PR #10 shows
the other half of the story — RuleHawk is also the fast *yes* on a good change.

## Try it locally (60 seconds)

```bash
pipx install git+https://github.com/optimesh-ai/RuleHawk
git clone https://github.com/optimesh-ai/rulehawk-demo && cd rulehawk-demo

# hygiene + PCI segmentation across all six vendors:
rulehawk gate 'network/*' --policy policy/segmentation.json --fail-on high

# prove the Zscaler egress flows actually work:
rulehawk gate network/edge-asa.cfg --policy policy/egress-edge.json --fail-on high
```

Or paste any file from `network/` into the zero-install
**[browser demo](https://optimesh-ai.github.io/RuleHawk/)** — analysis runs
client-side; the config never leaves your machine.

## What's in the repo

```
network/                     one estate, six vendor syntaxes — one gate
  edge-asa.cfg                 Cisco ASA   (internet edge, Zscaler egress path)
  core-ios.acl                 Cisco IOS   (the PCI / CORP / OT zone boundary)
  dc-nxos.acl                  Cisco NX-OS (datacenter ToR)
  branch-junos.conf            Junos       (branch uplink filter)
  dc-panos.set                 PAN-OS      (datacenter east-west)
  egress-iptables.rules        iptables    (Linux egress gateway)
policy/
  segmentation.json            what must NEVER be reachable (PCI, OT isolation)
  egress-edge.json             what MUST be reachable (ZEN ranges, GRE, IPsec)
  egress-host.json             the browser flows the Linux gateway must forward
tools/update_zscaler_zones.py  refreshes ZEN ranges from Zscaler's published feed
.github/workflows/
  rulehawk.yml                 the PR gate (this is all the setup there is)
  zscaler-refresh.yml          weekly: feed changed -> PR -> gate re-proves egress
```

**Why connectivity policies are scoped per config:** `must_reach` proves a flow
against *every* audited config — and a branch filter is not supposed to reach
the ZEN ranges. So the gate runs the segmentation policy across everything, and
each connectivity policy only against the configs that own that path. Two jobs,
four lines of YAML each.

**Why the weekly refresh matters:** Zscaler expands its enforcement-node ranges;
an egress rule proven last quarter can silently miss a new range. The cron job
pulls the published feed, opens a PR when it changes, and the gate on that PR
*proves* whether your firewalls already cover the new ranges — continuous egress
readiness, no live probes, no credentials.

## Adopt it in your repo

```yaml
permissions: { contents: read, security-events: write, pull-requests: write }
steps:
  - uses: actions/checkout@v4
  - uses: optimesh-ai/RuleHawk@v1
    with:
      configs: firewall/**/*.conf
      policy: .rulehawk/policy.json
      fail-on: high
```

Full inputs/outputs: [RuleHawk Action docs](https://github.com/optimesh-ai/RuleHawk/blob/main/docs/github-action.md) ·
policy schema: [policy reference](https://github.com/optimesh-ai/RuleHawk/blob/main/docs/policy.md)

**Scope, honestly:** RuleHawk proves the *filter layer* — it does not model
routing, NAT, or the proxy itself. `connectivity-ok` means "your firewalls don't
block it"; pair with a forwarding-model tool for end-to-end path proofs.
