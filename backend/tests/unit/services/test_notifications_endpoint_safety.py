import socket

import pytest

from config import Settings
from services.notifications.endpoint_safety import PushEndpointRejectedError, validate_push_endpoint

_PUBLIC_IPV4 = [(socket.AF_INET, None, None, "", ("142.250.0.1", 0))]
_PRIVATE_IPV4 = [(socket.AF_INET, None, None, "", ("10.0.0.5", 0))]
_LOOPBACK_IPV4 = [(socket.AF_INET, None, None, "", ("127.0.0.1", 0))]
_LINK_LOCAL_IPV4 = [(socket.AF_INET, None, None, "", ("169.254.1.1", 0))]


def _settings(allowed_hosts: str = "*.googleapis.com,web.push.apple.com") -> Settings:
    return Settings(push_allowed_hosts=allowed_hosts)


class TestValidatePushEndpoint:
    def test_rejects_non_https_scheme(self):
        with pytest.raises(PushEndpointRejectedError, match="https"):
            validate_push_endpoint("http://fcm.googleapis.com/send/abc", _settings())

    def test_rejects_host_outside_allowlist(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _PUBLIC_IPV4)
        with pytest.raises(PushEndpointRejectedError, match="allowlist"):
            validate_push_endpoint("https://evil.example.com/send/abc", _settings())

    def test_wildcard_requires_a_subdomain(self, monkeypatch):
        # "*.googleapis.com" must not match the bare apex domain - only a real subdomain.
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _PUBLIC_IPV4)
        with pytest.raises(PushEndpointRejectedError, match="allowlist"):
            validate_push_endpoint("https://googleapis.com/send/abc", _settings())

    def test_accepts_a_matching_subdomain_with_a_public_ip(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _PUBLIC_IPV4)
        validate_push_endpoint("https://fcm.googleapis.com/send/abc", _settings())

    def test_accepts_an_exact_non_wildcard_allowlist_entry(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _PUBLIC_IPV4)
        validate_push_endpoint("https://web.push.apple.com/send/abc", _settings())

    def test_rejects_a_private_ip(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _PRIVATE_IPV4)
        with pytest.raises(PushEndpointRejectedError, match="non-public"):
            validate_push_endpoint("https://fcm.googleapis.com/send/abc", _settings())

    def test_rejects_a_loopback_ip(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _LOOPBACK_IPV4)
        with pytest.raises(PushEndpointRejectedError, match="non-public"):
            validate_push_endpoint("https://fcm.googleapis.com/send/abc", _settings())

    def test_rejects_a_link_local_ip(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _LINK_LOCAL_IPV4)
        with pytest.raises(PushEndpointRejectedError, match="non-public"):
            validate_push_endpoint("https://fcm.googleapis.com/send/abc", _settings())

    def test_rejects_when_dns_resolution_fails(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise socket.gaierror("not found")

        monkeypatch.setattr(socket, "getaddrinfo", _raise)
        with pytest.raises(PushEndpointRejectedError, match="resolve"):
            validate_push_endpoint("https://fcm.googleapis.com/send/abc", _settings())

    def test_rejects_a_url_with_no_host(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _PUBLIC_IPV4)
        with pytest.raises(PushEndpointRejectedError, match="no host"):
            validate_push_endpoint("https:///send/abc", _settings())
