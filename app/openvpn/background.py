"""Background task: poll OpenVPN management and send to WebSocket clients."""
import asyncio
import time
from app.openvpn.config import OPENVPN_POLL_INTERVAL
from app.openvpn.traffic import fetch_openvpn_status, parse_clients


def _enrich_client(c: dict, last_snapshot: dict) -> dict:
    """
    Compute delta bytes and speed (bps/kbps) like openvpn-collector.
    """
    key = c["common_name"]
    now = time.time()
    prev = last_snapshot.get(key)

    if prev is not None:
        delta_time = now - prev.get("timestamp", now)
        if delta_time <= 0:
            delta_time = 1e-6
        delta_in = c["bytes_received"] - prev.get("bytes_received", 0)
        delta_out = c["bytes_sent"] - prev.get("bytes_sent", 0)
        speed_in = delta_in / delta_time
        speed_out = delta_out / delta_time
    else:
        delta_in = delta_out = 0
        speed_in = speed_out = 0.0

    return {
        **c,
        "delta_bytes_in": delta_in,
        "delta_bytes_out": delta_out,
        "speed_in_bps": round(speed_in, 2),
        "speed_out_bps": round(speed_out, 2),
        "speed_in_kbps": round(speed_in / 1024, 2),
        "speed_out_kbps": round(speed_out / 1024, 2),
        "timestamp": now,
        "online": True,
    }


async def openvpn_traffic_poller(state: dict):
    """
    state["traffic_snapshot"] = { common_name: enriched_client_dict }
    state["traffic_ws_clients"] = list of (websocket, username)
    """
    last_snapshot = state.setdefault("traffic_last_snapshot", {})
    clients_list = state.setdefault("traffic_ws_clients", [])
    interval = OPENVPN_POLL_INTERVAL

    while True:
        try:
            status_text = await fetch_openvpn_status()
            clients = parse_clients(status_text)
            new_snapshot = {}

            for c in clients:
                enriched = _enrich_client(c, last_snapshot)
                new_snapshot[c["common_name"]] = enriched
                last_snapshot[c["common_name"]] = enriched

            state["traffic_snapshot"] = new_snapshot
            state["traffic_last_snapshot"] = last_snapshot

            if clients_list:
                to_remove = []
                for i, (ws, username) in enumerate(clients_list):
                    data = new_snapshot.get(username)
                    if data is None:
                        data = {
                            "common_name": username,
                            "real_ip": None,
                            "virtual_ip": None,
                            "bytes_received": 0,
                            "bytes_sent": 0,
                            "connected_since": None,
                            "connected_since_epoch": 0,
                            "cipher": None,
                            "online": False,
                            "delta_bytes_in": 0,
                            "delta_bytes_out": 0,
                            "speed_in_bps": 0,
                            "speed_out_bps": 0,
                            "speed_in_kbps": 0,
                            "speed_out_kbps": 0,
                            "timestamp": time.time(),
                        }
                    try:
                        await ws.send_json(data)
                    except Exception:
                        to_remove.append(i)
                for i in reversed(to_remove):
                    clients_list.pop(i)
        except Exception:
            pass
        await asyncio.sleep(interval)
