import os
from app.openvpn.config import IP_POOLS, VPN_NET_PREFIX, CCD_DIR


def get_used_ips() -> set[str]:
    used: set[str] = set()
    if not os.path.exists(CCD_DIR):
        return used
    for fname in os.listdir(CCD_DIR):
        path = os.path.join(CCD_DIR, fname)
        try:
            with open(path) as f:
                for line in f:
                    if line.startswith("ifconfig-push"):
                        parts = line.split()
                        if len(parts) >= 2:
                            used.add(parts[1])
        except (OSError, IOError):
            continue
    return used


def allocate_ip(role: str) -> str:
    if role not in IP_POOLS:
        raise ValueError(f"Unknown VPN role: {role}. Valid: {list(IP_POOLS.keys())}")
    used_ips = get_used_ips()
    for host in IP_POOLS[role]:
        ip = f"{VPN_NET_PREFIX}{host}"
        if ip not in used_ips:
            return ip
    raise RuntimeError(f"No available IP in pool for role: {role}")
