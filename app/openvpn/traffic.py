"""
Fetch OpenVPN client status from management interface (status 3).
Used for traffic I/O (bytes_received, bytes_sent) per client.
"""
import asyncio
from app.openvpn.config import OPENVPN_MANAGEMENT_HOST, OPENVPN_MANAGEMENT_PORT


async def fetch_openvpn_status() -> str:
    """Read status 3 (client list) from OpenVPN management. TAB-separated."""
    reader, writer = await asyncio.open_connection(
        OPENVPN_MANAGEMENT_HOST, OPENVPN_MANAGEMENT_PORT
    )
    try:
        await reader.read(1024)  # banner
        writer.write(b"status 3\r\n")
        await writer.drain()
        data = await reader.readuntil(b"END\r\n")
        return data.decode(errors="ignore")
    finally:
        writer.close()
        await writer.wait_closed()


def parse_clients(status_text: str) -> list[dict]:
    """Parse CLIENT_LIST from status 3 output (TAB-separated)."""
    clients = []
    for line in status_text.splitlines():
        if not line.startswith("CLIENT_LIST"):
            continue
        p = line.split("\t")
        if len(p) < 12:
            continue
        clients.append({
            "common_name": p[1],
            "real_ip": p[2].split(":")[0],
            "virtual_ip": p[3],
            "bytes_received": int(p[5]),
            "bytes_sent": int(p[6]),
            "connected_since": p[7],
            "connected_since_epoch": int(p[8]),
            "cipher": p[-1],
        })
    return clients
