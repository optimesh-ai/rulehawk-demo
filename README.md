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

Three pull requests are permanently open in this repo, each a realistic bad change
held at the gate. Open one and look at the checks + the review comment:

| PR | The change | What RuleHawk says |
|---|---|---|
| **The PCI leak** | "Temporarily" allow CORP → PCI on 445 for a file-share migration | 🔴 `SEGMENTATION VIOLATION (CORP must not reach PCI): the ACL PERMITS 10.20.0.1 -> 10.10.0.1:445 (tcp)` — with the paste-ready deny that fixes it |
| **The broken tunnel** | Tidy-up removes the "unused" UDP 4500 permit | 🔴 `CONNECTIVITY BROKEN … no ruleset permits ANY packet of 192.0.2.0/29 -> ZEN:4500` — IPsec NAT-T would have died in production; 500 still being open is *not* accepted as proof for 4500 |
| **The phantom block** | An "emergency block" deny added *below* the permit that already matches the traffic | 🔴 `This deny NEVER takes effect — the traffic you meant to block is ALLOWED` (intent-inversion, critical) |

Merges are blocked; the sticky review comment carries the witness packets; the
Security tab gets SARIF annotations on the exact lines.

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
