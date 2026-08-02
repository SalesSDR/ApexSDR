"""Sprint 7.1: SSRF protection for the one place this codebase fetches a
URL supplied by an inbound webhook request (Twilio's `RecordingUrl` form
field) rather than one it constructed itself. Without this, a forged or
replayed webhook could point `RecordingUrl` at an attacker-controlled
server and the backend would fetch it WITH the real Twilio Account SID/
Auth Token attached as Basic Auth (services/voice_ai/stt/production.py) -
handing the attacker live Twilio credentials.

Defense in depth, in order: HTTPS-only, exact-hostname allowlist (only
Twilio's own recording-media host), reject any URL carrying embedded
credentials, and reject a hostname that resolves to a private/loopback/
link-local/reserved IP (guards against DNS rebinding even though the
hostname is already pinned to a real Twilio domain).
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

# Twilio serves call recordings from this host regardless of account/region -
# see twilio.com/docs/voice/api/recording. Only https:// + this exact host
# is ever fetched; nothing else, no matter what a request claims.
ALLOWED_RECORDING_HOSTS = frozenset({"api.twilio.com"})


class UntrustedRecordingURLError(ValueError):
    """Raised when a RecordingUrl fails SSRF validation. Callers must treat
    this exactly like any other transcription failure (log and degrade to
    silence) - never retry with a relaxed check."""


def _validate_no_embedded_credentials(parsed) -> None:
    if parsed.username or parsed.password:
        raise UntrustedRecordingURLError("Recording URL must not contain embedded credentials")


async def validate_recording_url(url: str) -> None:
    """Raises UntrustedRecordingURLError if `url` is not a plain https://
    link to Twilio's recording host resolving to a public IP address."""
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise UntrustedRecordingURLError(f"Recording URL must use HTTPS, got scheme={parsed.scheme!r}: {url}")

    if parsed.hostname not in ALLOWED_RECORDING_HOSTS:
        raise UntrustedRecordingURLError(
            f"Recording URL host {parsed.hostname!r} is not in the allowlist {sorted(ALLOWED_RECORDING_HOSTS)}"
        )

    _validate_no_embedded_credentials(parsed)

    try:
        addrinfo = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443)
    except socket.gaierror as e:
        raise UntrustedRecordingURLError(f"Could not resolve recording URL host {parsed.hostname!r}: {e}") from e

    for family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise UntrustedRecordingURLError(
                f"Recording URL host {parsed.hostname!r} resolved to a non-public address: {ip}"
            )
