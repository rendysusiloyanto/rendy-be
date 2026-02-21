from app.ukk_runner.utils.ssh import SSHClient


class WebServerChecker:
    def __init__(self, vm_ssh_connection):
        self.vm_ssh_connection = vm_ssh_connection

    def check_nginx_binary(self, expected_path="nginx"):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run(f"which {expected_path}")
            found = bool(res.get_output().strip())
            path = res.get_output().strip() if found else None
        except Exception:
            found = False
            path = None
        return {
            "step": "4.A Checking Nginx Binary",
            "status": found,
            "path": path,
            "message": None if found else "Nginx binary not found",
        }

    def check_nginx_service(self):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run("systemctl is-active nginx")
            active = res.get_output().strip() == "active"
        except Exception:
            active = False
        return {
            "step": "4.B Checking Nginx Service",
            "status": active,
            "value": active,
            "message": None if active else "Nginx service not running",
        }

    def check_nginx_config_syntax(self):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run("sudo -S -p '' nginx -t", use_sudo=True)
            output = res.get_output() + res.get_error()
            success = "syntax is ok" in output and "test is successful" in output
            return {
                "step": "4.D Checking Nginx Config Syntax",
                "status": success,
                "output": output.strip(),
                "message": None if success else "Nginx configuration test failed",
            }
        except Exception as e:
            return {
                "step": "4.D Checking Nginx Config Syntax",
                "status": False,
                "output": None,
                "message": str(e),
            }
