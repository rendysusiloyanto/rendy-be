from app.ukk_runner.utils.ssh import SSHClient


class WebServerChecker:
    def __init__(self, vm_ssh_connection):
        self.vm_ssh_connection = vm_ssh_connection

    def check_nginx_binary(self, expected_path="nginx"):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run(f"which {expected_path}")
            out, err = res.get_output(), res.get_error()
            found = bool(out.strip())
            path = out.strip() if found else None
            cmd_out = (out + "\n" + err).strip() or None
        except Exception:
            found = False
            path = None
            cmd_out = None
        return {
            "step": "4.A Checking Nginx Binary",
            "status": found,
            "path": path,
            "message": None if found else "Nginx binary not found",
            "command_output": cmd_out,
        }

    def check_nginx_service(self):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run("systemctl is-active nginx")
            active = res.get_output().strip() == "active"
            status_res = ssh.run("systemctl status nginx --no-pager", use_sudo=True)
            system_output = (status_res.get_output() + "\n" + status_res.get_error()).strip()
        except Exception:
            active = False
            system_output = None
        return {
            "step": "4.B Checking Nginx Service",
            "status": active,
            "value": active,
            "message": None if active else "Nginx service not running",
            "system_output": system_output,
        }

    def check_nginx_config_syntax(self):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run("sudo -S -p '' nginx -t", use_sudo=True)
            output = (res.get_output() + "\n" + res.get_error()).strip()
            success = "syntax is ok" in output and "test is successful" in output
            return {
                "step": "4.D Checking Nginx Config Syntax",
                "status": success,
                "output": output,
                "system_output": output,
                "message": None if success else "Nginx configuration test failed",
            }
        except Exception as e:
            return {
                "step": "4.D Checking Nginx Config Syntax",
                "status": False,
                "output": None,
                "message": str(e),
            }
