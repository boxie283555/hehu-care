"""Local network discovery and the optional externally accessible origin."""
import ipaddress
import os
import socket
from urllib.parse import urlsplit


def public_base():
    value = os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/')
    if not value:
        return ''
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('PUBLIC_BASE_URL 必须是完整站点地址，例如 https://care.example.com，不能包含路径或账号')
    return value


def lan_addresses():
    candidates = set()
    try:
        candidates.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    # UDP connect selects a route; no application data is sent.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 80))
            candidates.add(sock.getsockname()[0])
    except OSError:
        pass
    return sorted(ip for ip in candidates if ipaddress.ip_address(ip).is_private
                  and not ipaddress.ip_address(ip).is_loopback
                  and not ipaddress.ip_address(ip).is_link_local
                  and not ipaddress.ip_address(ip).is_unspecified)


def sharing_config(host, port):
    candidates = lan_addresses()
    if host not in ('127.0.0.1', 'localhost', '0.0.0.0'):
        candidates = [host]
    return {'bind_host': host, 'port': port, 'public_base': public_base(),
            'lan_enabled': host not in ('127.0.0.1', 'localhost'),
            'lan_urls': ['http://%s:%s' % (ip, port) for ip in candidates]}
