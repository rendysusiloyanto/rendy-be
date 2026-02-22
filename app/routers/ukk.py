"""
UKK Test Service: nodes (admin) + WebSocket run test.
TestRunner dijalankan dari app.ukk_runner (tanpa dependensi path luar).
Client bisa kirim { "action": "cancel" } untuk membatalkan test.
"""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from app.auth import get_current_user_admin, get_user_from_token
from app.database import get_db
from app.models.proxmox_node import ProxmoxNode
from app.schemas.ukk import ProxmoxNodeCreate, ProxmoxNodeResponse
from app.ukk_runner import TestRunner, TestStopException

router = APIRouter(prefix="/api/ukk", tags=["ukk"])
_executor = ThreadPoolExecutor(max_workers=2)


# ---------- Nodes (Admin only) ----------

@router.get("/nodes", response_model=list[ProxmoxNodeResponse])
def list_nodes(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    """Daftar node Proxmox. Hanya admin."""
    nodes = db.query(ProxmoxNode).order_by(ProxmoxNode.created_at.desc()).all()
    return [
        ProxmoxNodeResponse(
            id=n.id,
            host=n.host,
            user=n.user,
            password=n.password,
            created_at=n.created_at.isoformat(),
        )
        for n in nodes
    ]


@router.post("/nodes", response_model=ProxmoxNodeResponse)
def create_node(
    body: ProxmoxNodeCreate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    """Tambah node Proxmox. Hanya admin."""
    node = ProxmoxNode(host=body.host, user=body.user, password=body.password)
    db.add(node)
    db.commit()
    db.refresh(node)
    return ProxmoxNodeResponse(
        id=node.id,
        host=node.host,
        user=node.user,
        password=node.password,
        created_at=node.created_at.isoformat(),
    )


@router.delete("/nodes/{node_id}")
def delete_node(
    node_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user_admin),
):
    """Hapus node Proxmox. Hanya admin."""
    node = db.query(ProxmoxNode).filter(ProxmoxNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node tidak ditemukan")
    db.delete(node)
    db.commit()
    return {"message": "Node dihapus"}


# ---------- WebSocket Run Test ----------

@router.websocket("/test/ws")
async def ukk_test_websocket(websocket: WebSocket):
    """
    Terima: { "token": "JWT", "data": { ... } } (data = payload test seperti index.html).
    Nodes diambil dari DB. Hasil test dikirim per event.
    """
    await websocket.accept()

    try:
        raw = await websocket.receive_json()
    except Exception:
        await websocket.close(code=4001)
        return

    token = raw.get("token")
    data = raw.get("data")
    if not token or not data:
        await websocket.send_json({"event": "error", "message": "token dan data wajib"})
        await websocket.close(code=4000)
        return

    db = next(get_db())
    try:
        user = get_user_from_token(token, db)
        if not user:
            await websocket.send_json({"event": "error", "message": "Token tidak valid"})
            await websocket.close(code=4003)
            return
    finally:
        db.close()

    db2 = next(get_db())
    try:
        nodes_list = list(
            db2.query(ProxmoxNode).order_by(ProxmoxNode.created_at.asc()).all()
        )
        nodes = [{"host": n.host, "user": n.user, "password": n.password} for n in nodes_list]
    finally:
        db2.close()

    if not nodes:
        await websocket.send_json({
            "event": "error",
            "message": "Belum ada node Proxmox. Admin harus menambah node dulu.",
        })
        await websocket.close(code=4000)
        return

    queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    cancel_event = threading.Event()

    def run_sync():
        try:
            runner = TestRunner(data, nodes)
            for r in runner.run():
                if cancel_event.is_set():
                    loop.call_soon_threadsafe(queue.put_nowait, ("_stop", "Test dibatalkan oleh user."))
                    return
                loop.call_soon_threadsafe(queue.put_nowait, r)
            loop.call_soon_threadsafe(queue.put_nowait, ("_stop", None))
        except TestStopException as e:
            loop.call_soon_threadsafe(queue.put_nowait, ("_stop", str(e)))
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, ("_stop", str(e)))

    future = loop.run_in_executor(_executor, run_sync)
    stop_error = None

    async def cancel_listener():
        try:
            while True:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=3600)
                if isinstance(msg, dict) and msg.get("action") == "cancel":
                    cancel_event.set()
                    break
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            pass

    listener_task = asyncio.create_task(cancel_listener())
    try:
        while True:
            item = await queue.get()
            if isinstance(item, tuple) and item[0] == "_stop":
                stop_error = item[1]
                break
            try:
                await websocket.send_json(item)
            except Exception:
                break
    except Exception as e:
        try:
            await websocket.send_json({"event": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
        await future

    if stop_error:
        try:
            await websocket.send_json({"event": "error", "message": stop_error})
        except Exception:
            pass

    try:
        await websocket.close()
    except Exception:
        pass
