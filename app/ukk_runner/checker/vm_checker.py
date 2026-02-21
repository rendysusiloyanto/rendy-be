from app.ukk_runner.utils.ssh import SSHClient
from app.ukk_runner.utils.parser import parse_vm_config


class VMChecker:
    def __init__(self, ssh_clients):
        self.ssh_clients = ssh_clients

    def find_vm(self, vm_name):
        for ssh in self.ssh_clients:
            cmd = "hostname && qm list"
            res = ssh.run(cmd)
            lines = res.get_output().splitlines()
            if not lines:
                continue
            hostname = lines[0].strip()
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == vm_name:
                    vmid = parts[0]
                    return {
                        "node_ssh_connection": ssh,
                        "hostname": hostname,
                        "vmid": vmid,
                    }
            ssh.close()
        return None

    def check_resources(self, node_ssh_connection, vmid):
        ssh = node_ssh_connection
        config_path = f"/etc/pve/qemu-server/{vmid}.conf"
        res = ssh.run(f"cat {config_path}")
        return parse_vm_config(res.get_output())

    def check_status(self, node_ssh_connection, vmid):
        ssh = node_ssh_connection
        res = ssh.run(f"qm status {vmid}")
        for line in res.get_output().splitlines():
            if line.startswith("status:"):
                return line.split(":")[1].strip()
        return "unknown"
