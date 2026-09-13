"""
Agent package.

Some networks (including the one this was built on) resolve IPv6 addresses they can't route, so
every new HTTPS connection stalls 10-20s on IPv6 before falling back to IPv4. Measured: a GitHub
README fetch took 10.3s by default and 0.3s over IPv4. Every host this agent reaches through
`requests` (GitHub, job boards, OpenRouter, Slack, HubSpot) serves IPv4, so prefer it for the
whole process. Set ALLOW_IPV6=1 to keep the default behavior.
"""
import os
import socket

# Where runtime files go: run log, mock app outputs, caches. Serverless hosts (Vercel) only allow writes under /tmp,
# so they get a /tmp folder; locally it stays eval/logs. Override with DATA_DIR.
DATA_DIR = os.getenv("DATA_DIR") or (os.path.join("/tmp", "honest-apply") if os.getenv("VERCEL") else os.path.join("eval", "logs"))

if os.getenv("ALLOW_IPV6", "").strip() != "1":
    import urllib3.util.connection as _urllib3_connection

    # ponytail: process-wide IPv4 preference for requests/urllib3 only (Composio's httpx client is unaffected);
    # drop it on hosts with working IPv6 if an IPv6-only endpoint is ever needed
    _urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
