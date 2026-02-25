import subprocess
from urllib.parse import parse_qs
from fastapi import APIRouter, Depends, HTTPException, Request, status, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from app.auth import require_not_blacklisted, get_user_from_token
from app.database import get_db
from app.models.user import User
from app.openvpn import create_openvpn_client, read_openvpn_client, get_openvpn_status
from app.openvpn.openvpn import sanitize_username

router = APIRouter(prefix="/api/openvpn", tags=["openvpn"])


@router.get("/status")
def get_status(user: User = Depends(require_not_blacklisted)):
    """
    Cek apakah user sudah punya config OpenVPN. Email diambil dari session.
    Untuk semua user (premium/non-premium) selama tidak blacklist.
    """
    email = user.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email tidak ditemukan di session.",
        )
    try:
        return get_openvpn_status(email=email)
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal cek status: {e!s}",
        )


def _vpn_role(user: User) -> str:
    """Map class_name ke role pool OpenVPN. Default GUEST."""
    name = (user.class_name or "").strip().upper().replace(" ", "_")
    from app.openvpn.config import IP_POOLS
    if name in IP_POOLS:
        return name
    return "GUEST"


@router.post("/create")
def create_config(user: User = Depends(require_not_blacklisted)):
    """
    Buat config OpenVPN untuk user yang login. Email diambil dari session.
    Untuk semua user (premium/non-premium) selama tidak blacklist. Gagal jika config sudah ada.
    """
    email = user.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email tidak ditemukan di session.",
        )
    vpn_status = get_openvpn_status(email=email)
    if vpn_status.get("has_config"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Config OpenVPN sudah ada. Gunakan tombol Download.",
        )
    try:
        role = _vpn_role(user)
        result = create_openvpn_client(email=email, role=role)
        return {
            "message": "Config OpenVPN berhasil dibuat.",
            "username": result["username"],
            "ip": result["ip"],
        }
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal membuat sertifikat OpenVPN. Hubungi admin.",
        )
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sistem: {e!s}",
        )


@router.get("/config", response_class=Response)
def get_config(user: User = Depends(require_not_blacklisted)):
    """
    Download file .ovpn untuk user yang login. Email diambil dari session.
    Untuk semua user (premium/non-premium) selama tidak blacklist.
    """
    email = user.email
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email tidak ditemukan di session.",
        )
    try:
        content = read_openvpn_client(email=email)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membaca file: {e!s}",
        )

    filename = f"{user.email.split('@')[0].replace('.', '_')}.ovpn"
    return Response(
        content=content,
        media_type="application/x-openvpn-profile",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/traffic")
def get_traffic(request: Request, user: User = Depends(require_not_blacklisted)):
    """
    Traffic I/O terbaru untuk user (username = email). Hanya untuk akun premium.
    Return null jika client belum terhubung ke VPN.
    """
    email = user.email
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email tidak ditemukan.")
    username = sanitize_username(email)
    state = getattr(request.app.state, "openvpn_traffic", None) or {}
    snapshot = state.get("traffic_snapshot", {})
    data = snapshot.get(username)
    if data is None:
        return {"connected": False, "bytes_received": 0, "bytes_sent": 0}
    return {
        "connected": True,
        "common_name": data.get("common_name"),
        "virtual_ip": data.get("virtual_ip"),
        "bytes_received": data.get("bytes_received", 0),
        "bytes_sent": data.get("bytes_sent", 0),
        "connected_since": data.get("connected_since"),
    }


@router.websocket("/traffic/ws")
async def traffic_websocket(websocket: WebSocket):
    """
    WebSocket untuk realtime traffic. Query: token=JWT.
    Untuk semua user (premium/non-premium) selama tidak blacklist.
    """
    await websocket.accept()
    query_string = websocket.scope.get("query_string", b"").decode()
    params = parse_qs(query_string)
    token_list = params.get("token", [])
    token = token_list[0] if token_list else None

    if not token:
        await websocket.close(code=4001)
        return

    db = next(get_db())
    try:
        user = get_user_from_token(token, db)
        if not user:
            await websocket.close(code=4003)
            return
        if user.is_blacklisted:
            await websocket.close(code=4003)
            return
        username = sanitize_username(user.email)
    finally:
        db.close()

    state = getattr(websocket.app.state, "openvpn_traffic", None)
    if state is None:
        await websocket.close(code=1011)
        return
    clients_list = state.get("traffic_ws_clients", [])
    clients_list.append((websocket, username))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        try:
            clients_list.remove((websocket, username))
        except ValueError:
            pass
