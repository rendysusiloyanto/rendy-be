"""
Convert uploaded videos to HLS and DASH using FFmpeg for adaptive streaming.
See: https://dev.to/ethand91/flask-video-streaming-app-tutorial-1dm3
"""
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

HLS_PLAYLIST = "playlist.m3u8"
DASH_MANIFEST = "manifest.mpd"


def convert_to_hls(input_path: Path, output_dir: Path) -> bool:
    """Convert video to HLS format using FFmpeg. Returns True on success."""
    output_dir.mkdir(parents=True, exist_ok=True)
    hls_playlist = output_dir / HLS_PLAYLIST

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-profile:v", "baseline",
        "-level", "3.0",
        "-start_number", "0",
        "-hls_time", "10",
        "-hls_list_size", "0",
        "-f", "hls",
        str(hls_playlist),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=3600)
        logger.info("HLS conversion completed for %s", input_path)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("HLS conversion failed for %s: %s", input_path, e.stderr and e.stderr.decode() or e)
        return False
    except subprocess.TimeoutExpired:
        logger.error("HLS conversion timed out for %s", input_path)
        return False
    except FileNotFoundError:
        logger.error("ffmpeg not found; install FFmpeg to enable HLS/DASH conversion")
        return False


def convert_to_dash(input_path: Path, output_dir: Path) -> bool:
    """Convert video to DASH format using FFmpeg. Returns True on success."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dash_playlist = output_dir / DASH_MANIFEST

    # Use 0:a? so audio is optional (videos without audio still convert)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-map", "0:v", "-map", "0:a?",
        "-c:v", "libx264",
        "-x264-params", "keyint=60:min-keyint=60:no-scenecut=1",
        "-b:v:0", "1500k",
        "-c:a", "aac", "-b:a", "128k",
        "-bf", "1", "-keyint_min", "60",
        "-g", "60", "-sc_threshold", "0",
        "-f", "dash",
        "-use_template", "1", "-use_timeline", "1",
        "-init_seg_name", "init-$RepresentationID$.m4s",
        "-media_seg_name", "chunk-$RepresentationID$-$Number%05d$.m4s",
        "-adaptation_sets", "id=0,streams=v id=1,streams=a",
        str(dash_playlist),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=3600)
        logger.info("DASH conversion completed for %s", input_path)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("DASH conversion failed for %s: %s", input_path, e.stderr and e.stderr.decode() or e)
        return False
    except subprocess.TimeoutExpired:
        logger.error("DASH conversion timed out for %s", input_path)
        return False
    except FileNotFoundError:
        logger.error("ffmpeg not found; install FFmpeg to enable HLS/DASH conversion")
        return False


def ensure_hls_dash_for_video(
    video_id: str,
    source_file_path: Path,
    streams_base_dir: Path,
) -> tuple[bool, bool]:
    """
    Convert a video to HLS and DASH. Creates streams_base_dir/video_id/hls and .../dash.
    Returns (hls_ok, dash_ok). If FFmpeg is missing, returns (False, False).
    """
    if not source_file_path.is_file():
        logger.warning("Source file not found for video %s: %s", video_id, source_file_path)
        return False, False

    video_stream_dir = streams_base_dir / video_id
    hls_dir = video_stream_dir / "hls"
    dash_dir = video_stream_dir / "dash"

    hls_ok = convert_to_hls(source_file_path, hls_dir)
    dash_ok = convert_to_dash(source_file_path, dash_dir)

    return hls_ok, dash_ok
