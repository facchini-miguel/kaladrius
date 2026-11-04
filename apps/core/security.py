"""Client address used by the login brute-force protection (django-axes)."""

import ipaddress

# Anyone with IPv6 controls at least a /64 and often a /48 (free from tunnel brokers),
# so counting failures per full IPv6 address would let an attacker rotate addresses
# and get unlimited attempts. Failures are counted per /48 network instead. Lockouts
# are per username + network, so other users in the same network are not affected.
PREFIXO_IPV6 = 48


def ip_para_bloqueio(request):
    """REMOTE_ADDR for IPv4; the /48 network address for IPv6 (axes AXES_CLIENT_IP_CALLABLE)."""
    endereco = request.META.get("REMOTE_ADDR") or ""
    try:
        ip = ipaddress.ip_address(endereco)
    except ValueError:
        return endereco or None
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/{PREFIXO_IPV6}", strict=False).network_address)
    return str(ip)
