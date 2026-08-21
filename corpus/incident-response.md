# Incident Response Runbook (v6)
Severity levels: SEV-1 (customer-facing outage), SEV-2 (degradation), SEV-3 (internal).
A SEV-1 requires an incident commander within 15 minutes, a status-page update within 30,
and executive notification within 1 hour. The incident commander is the on-call SRE lead
unless explicitly handed off. Blameless postmortems are due within 5 business days for
SEV-1/2; action items are tracked to closure by the reliability guild. Communication
happens in the #inc-<number> channel only — side channels fragment the timeline. Legal
must be looped in before any external statement about data exposure.
