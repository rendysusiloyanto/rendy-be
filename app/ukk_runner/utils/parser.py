import re
from app.ukk_runner.utils.utils import timestamp_to_datetime, humanize_datetime


def parse_vm_config(config_text):
    data = {
        "cores": None,
        "memory": None,
        "disk_size": None,
        "iso_name": None,
        "created_at": None,
    }
    for line in config_text.splitlines():
        line = line.strip()
        if line.startswith("cores:"):
            data["cores"] = int(line.split(":")[1].strip())
        elif line.startswith("memory:"):
            data["memory"] = int(line.split(":")[1].strip())
        elif line.startswith("scsi0:"):
            match = re.search(r"size=([^,]+)", line)
            if match:
                data["disk_size"] = match.group(1)
        elif line.startswith("ide2:"):
            match = re.search(r"iso/([^,]+)", line)
            if match:
                data["iso_name"] = match.group(1)
        elif "ctime=" in line:
            match = re.search(r"ctime=(\d+)", line)
            if match:
                ts = int(match.group(1))
                data["created_at"] = humanize_datetime(timestamp_to_datetime(ts))
    return data
