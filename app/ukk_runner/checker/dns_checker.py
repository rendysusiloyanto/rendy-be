from app.ukk_runner.utils.ssh import SSHClient


class DNSChecker:
    def __init__(self, vm_ssh_connection):
        self.vm_ssh_connection = vm_ssh_connection

    def check_bind_binary(self):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run("which named")
            out, err = res.get_output(), res.get_error()
            found = bool(out.strip())
            return {
                "step": "7.A Checking DNS Binary",
                "status": found,
                "path": out.strip() if found else None,
                "message": None if found else "Bind9 binary not found",
                "command_output": (out + "\n" + err).strip() or None,
            }
        except Exception as e:
            return {"step": "7.A Checking DNS Binary", "status": False, "message": str(e)}

    def check_bind_service(self):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run("systemctl is-active bind9")
            active = res.get_output().strip() == "active"
            status_res = ssh.run("systemctl status bind9 --no-pager", use_sudo=True)
            system_output = (status_res.get_output() + "\n" + status_res.get_error()).strip()
            return {
                "step": "7.B Checking DNS Service",
                "status": active,
                "message": None if active else "Bind9 service not running",
                "system_output": system_output,
            }
        except Exception as e:
            return {"step": "7.B Checking DNS Service", "status": False, "message": str(e)}

    def check_forward_dns(self, domain, expected_ip):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run(f"dig {domain} @localhost +short")
            out, err = res.get_output(), res.get_error()
            resolved_ip = out.strip()
            correct = expected_ip in resolved_ip
            return {
                "step": "7.C Checking Forward DNS",
                "status": correct,
                "domain": domain,
                "expected_ip": expected_ip,
                "actual_ip": resolved_ip,
                "message": None if correct else "Forward DNS mismatch",
                "command_output": (out + "\n" + err).strip() or None,
            }
        except Exception as e:
            return {"step": "7.C Checking Forward DNS", "status": False, "message": str(e)}

    def check_reverse_dns(self, ip_address, expected_domain):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run(f"dig -x {ip_address} @localhost +short")
            out, err = res.get_output(), res.get_error()
            resolved_domain = out.strip()
            correct = expected_domain in resolved_domain
            return {
                "step": "7.D Checking Reverse DNS",
                "status": correct,
                "ip": ip_address,
                "expected_domain": expected_domain,
                "actual_domain": resolved_domain,
                "message": None if correct else "Reverse DNS mismatch",
                "command_output": (out + "\n" + err).strip() or None,
            }
        except Exception as e:
            return {"step": "7.D Checking Reverse DNS", "status": False, "message": str(e)}
