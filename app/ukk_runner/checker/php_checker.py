from app.ukk_runner.utils.ssh import SSHClient
from app.ukk_runner.utils.compare import compare


class PHPChecker:
    def __init__(self, vm_ssh_connection):
        self.vm_ssh_connection = vm_ssh_connection

    def check_php_binary(self, binary):
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run(f"which {binary}")
            found = bool(res.get_output().strip())
            path = res.get_output().strip() if found else None
        except Exception:
            found = False
            path = None
        return {
            "step": "3.A Checking PHP Binary",
            "status": found,
            "path": path,
            "message": None if found else "PHP binary not found",
        }

    def check_php_modules(self, modules_expected=None):
        if modules_expected is None:
            modules_expected = ["mysqli", "curl", "gd", "mbstring", "xml", "json", "zip", "openssl", "exif", "fileinfo", "intl"]
        if isinstance(modules_expected, dict):
            modules_expected = [k for k, v in modules_expected.items() if v]
        try:
            ssh = self.vm_ssh_connection
            res = ssh.run("php -m")
            installed = [line.strip() for line in res.get_output().splitlines() if line.strip()]
            comparison = {}
            for mod in modules_expected:
                comparison[mod] = {
                    "expected": True,
                    "actual": mod in installed,
                    "status": mod in installed,
                }
            all_ok = all(c["status"] for c in comparison.values())
        except Exception:
            comparison = {mod: {"expected": True, "actual": False, "status": False} for mod in modules_expected}
            all_ok = False
        return {
            "step": "3.B Checking PHP Modules",
            "status": all_ok,
            "modules": comparison,
        }
