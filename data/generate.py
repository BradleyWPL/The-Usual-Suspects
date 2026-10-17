"""Generate a deterministic, fictional IT service-desk dataset."""
from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20261016
CAUSES = [
    ("auth-cert", "Authentication gateway certificate rotation", "Auth Gateway", ["sign in keeps timing out", "login requests fail after redirect", "identity check is taking forever", "getting a gateway timeout when signing in", "authentication spins then fails"]),
    ("auth-pool", "Identity provider connection pool exhaustion", "Identity API", ["single sign on is very slow", "identity requests are backing up", "users cannot complete the sign in flow", "login response is delayed", "authentication service is not responding"]),
    ("pay-broker", "Payment broker partition rebalance", "Message Broker", ["payment confirmations are stuck in queue", "checkout is waiting on payment", "payment events are arriving late", "orders sit pending after payment", "payment processing is backing up"]),
    ("pay-ledger", "Ledger write contention after index change", "Ledger", ["payment writes are failing", "ledger updates are timing out", "checkout cannot save payment status", "settlement records are delayed", "payment database writes are blocked"]),
    ("report-query", "Warehouse query plan regression", "Warehouse", ["reports fail before finishing", "scheduled report is timing out", "analytics export keeps failing", "monthly report is stuck running", "report request returns a server error"]),
    ("vpn-policy", "Remote access policy mismatch", "VPN Gateway", ["vpn reconnects every few minutes", "remote access drops after login", "cannot keep a vpn session open", "connection loops back to sign in", "remote session disconnects repeatedly"]),
    ("inv-consumer", "Inventory event consumer backlog", "Event Bus", ["inventory count has not refreshed", "stock changes show up late", "product availability is stale", "inventory sync is falling behind", "catalog still shows the old quantity"]),
    ("search-shards", "Search index shard allocation failure", "Search Service", ["search returns no results", "catalog search is unavailable", "product lookup fails to load", "search page keeps spinning", "results disappeared from item search"]),
    ("mail-relay", "Outbound mail relay queue saturation", "Mail Relay", ["notification emails are delayed", "password reset message never arrives", "outbound email is still pending", "alerts are not reaching inboxes", "mail delivery is backed up"]),
    ("device-registry", "Device registry lookup latency", "Device Registry", ["device enrollment is stuck", "managed laptop is missing from inventory", "device check in is delayed", "registration request keeps timing out", "new device does not appear in console"]),
    ("storage-capacity", "Shared storage capacity threshold reached", "Shared Storage", ["shared files will not open", "upload fails on the team drive", "documents take too long to load", "file share reports unavailable", "saving to shared storage times out"]),
    ("dns-cache", "Stale service discovery cache", "Service Discovery", ["internal app cannot find its service", "requests resolve to the old endpoint", "service address lookup fails", "connection goes to a retired host", "internal endpoint is not resolving"]),
    ("billing-pool", "Billing database connection pool exhaustion", "Billing API", ["billing requests are waiting for a database connection", "invoice creation is timing out", "billing updates are backing up", "charges remain pending after checkout", "billing service cannot reach its database"]),
    ("edge-cert", "Edge certificate chain missing intermediate", "Customer Portal", ["customer portal warns that the connection is unsafe", "portal sign in fails certificate validation", "browser reports an invalid certificate chain", "portal requests fail during the tls handshake", "customers cannot open the secure portal"]),
    ("portal-cache", "Customer portal cache invalidation failure", "Customer Portal", ["portal shows outdated account details", "recent changes are missing from the dashboard", "customer profile updates are not appearing", "portal keeps displaying the previous balance", "account page has stale information"]),
]

SYSTEMS = [
    ("ci-auth-gw", "Auth Gateway", "application", "Identity"),
    ("ci-identity", "Identity API", "application", "Identity"),
    ("ci-session", "Session Store", "database", "Identity"),
    ("ci-directory", "Directory Service", "application", "Identity"),
    ("ci-payments", "Payment API", "application", "Payments"),
    ("ci-broker", "Message Broker", "middleware", "Payments"),
    ("ci-ledger", "Ledger", "database", "Payments"),
    ("ci-reporting", "Reporting Service", "application", "Analytics"),
    ("ci-warehouse", "Warehouse", "database", "Analytics"),
    ("ci-vpn", "VPN Gateway", "network", "Remote Access"),
    ("ci-device", "Device Registry", "application", "Endpoint"),
    ("ci-inventory", "Inventory API", "application", "Commerce"),
    ("ci-eventbus", "Event Bus", "middleware", "Commerce"),
    ("ci-search", "Search Service", "application", "Commerce"),
    ("ci-catalog", "Catalog API", "application", "Commerce"),
    ("ci-mail", "Mail Relay", "middleware", "Messaging"),
    ("ci-storage", "Shared Storage", "storage", "Workplace"),
    ("ci-discovery", "Service Discovery", "platform", "Platform"),
    ("ci-dns", "Internal DNS", "network", "Platform"),
    ("ci-metrics", "Metrics Collector", "platform", "Platform"),
    ("ci-billing", "Billing API", "application", "Payments"),
    ("ci-billing-db", "Billing Database", "database", "Payments"),
    ("ci-portal", "Customer Portal", "application", "Customer Experience"),
    ("ci-portal-cache", "Portal Cache", "database", "Customer Experience"),
    ("ci-ca", "Certificate Authority", "platform", "Platform"),
]

EDGES = [
    ("ci-directory", "ci-identity"), ("ci-identity", "ci-auth-gw"), ("ci-session", "ci-auth-gw"),
    ("ci-broker", "ci-payments"), ("ci-ledger", "ci-payments"),
    ("ci-warehouse", "ci-reporting"), ("ci-device", "ci-vpn"),
    ("ci-eventbus", "ci-inventory"), ("ci-catalog", "ci-search"),
    ("ci-dns", "ci-discovery"), ("ci-discovery", "ci-auth-gw"), ("ci-discovery", "ci-payments"),
    ("ci-metrics", "ci-reporting"),
    ("ci-billing-db", "ci-billing"), ("ci-ca", "ci-portal"), ("ci-portal-cache", "ci-portal"),
]
CAUSE_PARENTS = {
    "auth-cert": ["ci-identity"], "auth-pool": ["ci-directory"], "pay-broker": ["ci-broker"],
    "pay-ledger": ["ci-ledger"], "report-query": ["ci-warehouse"], "vpn-policy": ["ci-device"],
    "inv-consumer": ["ci-eventbus"], "search-shards": ["ci-catalog"], "mail-relay": ["ci-mail"],
    "device-registry": ["ci-device"], "storage-capacity": ["ci-storage"], "dns-cache": ["ci-dns"],
    "billing-pool": ["ci-billing-db"], "edge-cert": ["ci-ca"], "portal-cache": ["ci-portal-cache"],
}

def support_timestamp(start: datetime, rng: random.Random, days: int = 30) -> datetime:
    """Sample a busier weekday daytime hour and a quieter weekend/night period."""
    offsets = list(range(days))
    day_weights = [3.5 if (start + timedelta(days=offset)).weekday() < 5 else 1.0 for offset in offsets]
    day = rng.choices(offsets, weights=day_weights, k=1)[0]
    hour_weights = [0.35 if hour < 6 else 1.2 if hour < 8 else 4.2 if hour < 18 else 2.0 if hour < 21 else 0.6 for hour in range(24)]
    hour = rng.choices(range(24), weights=hour_weights, k=1)[0]
    return start + timedelta(days=day, hours=hour, minutes=rng.randrange(60), seconds=rng.randrange(60))

def add_text_noise(text: str, rng: random.Random) -> str:
    if rng.random() < 0.035:
        text = text.replace("service", "svc", 1).replace("connection", "conn", 1)
    if rng.random() < 0.025:
        words = text.split()
        candidates = [i for i, word in enumerate(words) if len(word) > 4]
        if candidates:
            position = rng.choice(candidates)
            word = words[position]
            words[position] = word[:2] + word[3] + word[2] + word[4:]
            text = " ".join(words)
    if rng.random() < 0.08:
        text = f"ALERT: {text} - automated monitor threshold exceeded"
    elif rng.random() < 0.16:
        text = text.capitalize()
    return text

def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def generate(output: Path, incidents_per_cause: int = 180, noise_count: int = 450) -> dict[str, int]:
    rng = random.Random(SEED)
    start = datetime(2026, 9, 16, tzinfo=timezone.utc)
    system_id = {name: ci for ci, name, _, _ in SYSTEMS}
    used_incident_ids: set[str] = set()

    def new_incident_id() -> str:
        # Random IDs avoid encoding cause, generation order, or noise membership.
        while True:
            value = f"INC-{rng.randrange(1_000_000_000):09d}"
            if value not in used_incident_ids:
                used_incident_ids.add(value)
                return value

    incident_rows: list[dict[str, object]] = []
    truth_rows: list[dict[str, object]] = []
    change_rows: list[dict[str, object]] = []
    cause_windows: dict[str, datetime] = {}

    # Event windows are intentionally staggered. A subset has no related change record.
    for number, (cause_id, summary, affected_name, phrases) in enumerate(CAUSES):
        incident_day = 26 if cause_id in {"edge-cert", "portal-cache"} else number * 2
        while (start + timedelta(days=incident_day)).weekday() >= 5:
            incident_day += 1
        onset = start + timedelta(days=incident_day, hours=rng.choices(range(24), weights=[0.35 if hour < 6 else 1.2 if hour < 8 else 4.2 if hour < 18 else 2.0 if hour < 21 else 0.6 for hour in range(24)], k=1)[0])
        cause_windows[cause_id] = onset
        affected_ci = system_id[affected_name]
        has_change = number % 4 != 3
        if has_change:
            change_rows.append({"change_id": f"CHG-{7000+number}", "ci_id": rng.choice(CAUSE_PARENTS[cause_id]),
                                "applied_at": (onset - timedelta(minutes=rng.randint(18, 95))).isoformat(),
                                "summary": summary, "risk": rng.choice(["low", "medium", "high"]), "outcome": "completed"})
        # An unrelated change is added near selected incidents to create a hard negative.
        if number % 3 == 1:
            change_rows.append({"change_id": f"CHG-{8000+number}", "ci_id": system_id["Metrics Collector"],
                                "applied_at": (onset - timedelta(minutes=35)).isoformat(),
                                "summary": "Routine telemetry agent maintenance", "risk": "low", "outcome": "completed"})
        for index in range(incidents_per_cause):
            if cause_id == "storage-capacity":
                opened = onset + timedelta(minutes=rng.randint(0, 14 * 24 * 60), seconds=rng.randint(0, 59))
            else:
                opened = onset + timedelta(minutes=int(rng.triangular(0, 1250, 260)), seconds=rng.randint(0, 59))
            phrase = rng.choice(phrases)
            host = f"{affected_name.lower().replace(' ', '-')}-{rng.randint(1, 28):02d}.corp.example"
            ticket = f"INC{rng.randint(100000, 999999)}"
            prefix = rng.choice(["", "please help: ", "urgent - ", "monitor alert: ", "seeing this again: "])
            suffix = rng.choice(["", " since this morning", " after reconnecting", " [retrying]", " - " + ticket])
            text = add_text_noise(f"{prefix}{phrase} on {host}{suffix}", rng)
            incident_id = new_incident_id()
            resolved = opened + timedelta(minutes=rng.randint(12, 420))
            incident_rows.append({"incident_id": incident_id, "opened_at": opened.isoformat(), "short_description": text,
                                  "description": f"{text}. Requester reports impact to {affected_name}; reference {ticket}.",
                                  "ci_id": affected_ci, "requester_id": f"REQ-{rng.randint(1, 420):04d}",
                                  "category": rng.choice(["application", "access", "network", "other"]),
                                  "priority": rng.choices([1, 2, 3, 4, 5], weights=[2, 12, 43, 33, 10])[0],
                                  "assignment_group": rng.choice(["Service Desk", "Platform Operations", "Business Applications"]),
                                  "state": "resolved", "resolved_at": resolved.isoformat()})
            truth_rows.append({"incident_id": incident_id, "cause_id": cause_id})

    # One-off requests have no recurring cause and should usually remain noise.
    actions = ["reset", "update", "add", "remove", "restore", "replace", "renew", "move", "install", "review", "rename", "archive"]
    resources = ["password", "calendar permission", "shared folder", "browser profile", "meeting room", "laptop dock",
                 "software license", "mailing list", "project workspace", "printer mapping", "mobile device", "team dashboard"]
    workspaces = ["atlas", "juniper", "northstar", "field-notes", "ledger-demo", "planning", "onboarding", "design-review",
                  "quarterly-close", "support-rotation", "inventory-audit", "release-checklist"]
    details = ["for a new starter", "before the review meeting", "for the regional team", "after a role change",
               "for next week's handoff", "while setting up a loaner", "for the afternoon workshop", "after a department move",
               "for the archived project", "while preparing a demo", "for a temporary assignment", "before travel"]
    ci_ids = [row[0] for row in SYSTEMS]
    for index in range(noise_count):
        opened = support_timestamp(start, rng)
        phrase = f"{rng.choice(actions)} {rng.choice(resources)} for {rng.choice(workspaces)} {rng.choice(details)}"
        incident_id = new_incident_id()
        text = f"{phrase} ({incident_id})"
        description = f"{text}. Request submitted through the employee support portal."
        if rng.random() < 0.12:
            description += f" Client address {rng.randint(10, 250)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}; observed at {opened.strftime('%Y-%m-%d %H:%M UTC')}."
        incident_rows.append({"incident_id": incident_id, "opened_at": opened.isoformat(), "short_description": text,
                              "description": description,
                              "ci_id": rng.choice(ci_ids), "requester_id": f"REQ-{rng.randint(1, 900):04d}",
                              "category": rng.choice(["access", "hardware", "software", "other"]),
                              "priority": rng.choices([1, 2, 3, 4, 5], weights=[1, 8, 37, 40, 14])[0],
                              "assignment_group": "Service Desk", "state": "resolved",
                              "resolved_at": (opened + timedelta(minutes=rng.randint(15, 600))).isoformat()})

    # Stable ordering makes regenerated CSVs byte-for-byte repeatable.
    incident_rows.sort(key=lambda row: str(row["opened_at"]))
    write_csv(output / "incidents.csv", list(incident_rows[0]), incident_rows)
    write_csv(output / "true_causes.csv", ["incident_id", "cause_id"], truth_rows)
    write_csv(output / "changes.csv", ["change_id", "ci_id", "applied_at", "summary", "risk", "outcome"], change_rows)
    write_csv(output / "configuration_items.csv", ["ci_id", "name", "ci_type", "service", "environment"],
              [{"ci_id": ci, "name": name, "ci_type": kind, "service": service, "environment": "simulated"} for ci, name, kind, service in SYSTEMS])
    write_csv(output / "ci_dependencies.csv", ["parent_ci_id", "child_ci_id"],
              [{"parent_ci_id": parent, "child_ci_id": child} for parent, child in EDGES])
    write_csv(output / "cause_catalog.csv", ["cause_id", "candidate_cause", "primary_ci_id"],
              [{"cause_id": cause_id, "candidate_cause": summary, "primary_ci_id": system_id[affected]} for cause_id, summary, affected, _ in CAUSES])
    # Keep raw labels outside feature files. The catalog is for candidate hypotheses, not incident features.
    return {"incidents": len(incident_rows), "known_cause_incidents": len(truth_rows), "one_off_incidents": noise_count,
            "causes": len(CAUSES), "changes": len(change_rows)}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "generated")
    parser.add_argument("--profile", choices=["quick", "benchmark"], default="quick",
                        help="quick runs in seconds; benchmark produces at least 30,000 incidents")
    parser.add_argument("--incidents-per-cause", type=int)
    parser.add_argument("--noise-count", type=int)
    args = parser.parse_args()
    per_cause = args.incidents_per_cause if args.incidents_per_cause is not None else (1000 if args.profile == "benchmark" else 180)
    noise_count = args.noise_count if args.noise_count is not None else (15000 if args.profile == "benchmark" else 450)
    if per_cause < 1 or noise_count < 0:
        parser.error("incident counts must be positive (noise may be zero)")
    counts = generate(args.output, per_cause, noise_count)
    print(f"Generated deterministic simulated dataset at {args.output}")
    print(" | ".join(f"{key}: {value:,}" for key, value in counts.items()))

if __name__ == "__main__":
    main()
