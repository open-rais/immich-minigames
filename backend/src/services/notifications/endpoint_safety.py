"""
SSRF guard for POST /notifications/subscriptions. That endpoint accepts a URL from the client
(the push subscription's `endpoint`) that the backend will later POST to (sender.py) - without
this, an authenticated user could register e.g. http://localhost:8000/... or an internal address
and turn the backend into a proxy into its own network. Three checks, cheapest first: scheme,
then the host allowlist, then a DNS resolution against private/loopback/link-local ranges (the
only one that costs a network round trip).
"""

import ipaddress
import socket
from urllib.parse import urlparse

from config import Settings


class PushEndpointRejectedError(Exception):
    """Raised by validate_push_endpoint - mapped to 400 by api/error_handlers.py."""


def validate_push_endpoint(endpoint: str, settings: Settings) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https":
        raise PushEndpointRejectedError("Push endpoint must use https")

    host = parsed.hostname
    if not host:
        raise PushEndpointRejectedError("Push endpoint has no host")

    if not any(_host_matches(host, pattern) for pattern in settings.push_allowed_host_patterns):
        raise PushEndpointRejectedError(f"Push endpoint host {host!r} is not in the allowlist")

    try:
        resolved = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise PushEndpointRejectedError(f"Could not resolve push endpoint host {host!r}") from exc

    for *_rest, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise PushEndpointRejectedError(
                f"Push endpoint host {host!r} resolves to a non-public address"
            )


def _host_matches(host: str, pattern: str) -> bool:
    if pattern.startswith("*."):
        suffix = pattern[1:]  # e.g. "*.googleapis.com" -> ".googleapis.com"
        return host.endswith(suffix) and len(host) > len(suffix)
    return host == pattern
