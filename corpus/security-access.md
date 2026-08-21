# Information Security & Access Policy (v7)
Access to production systems follows least privilege and is provisioned through AccessHub.
Standing production access is limited to the SRE on-call rotation; all other production
access is just-in-time, expires after 8 hours, and requires a ticket reference.
Contractors receive tier-C credentials: no production access, no customer PII, and VPN
access limited to their engagement's project VLAN. Badge sharing is a terminable offense.
Quarterly access reviews are owned by each system's data steward; unreviewed grants are
auto-revoked after 100 days. Security incidents must be reported to secops@ within 1 hour
of discovery — the clock starts at discovery, not confirmation.
