from app.ukk_runner.formatter import format_result
from app.ukk_runner.scoring import ScoreManager
from app.ukk_runner.checker.vm_checker import VMChecker
from app.ukk_runner.checker.php_checker import PHPChecker
from app.ukk_runner.checker.web_server import WebServerChecker
from app.ukk_runner.checker.mysql_checker import MySQLChecker
from app.ukk_runner.checker.wp_checker import WordPressChecker
from app.ukk_runner.checker.dns_checker import DNSChecker
from app.ukk_runner.exceptions import TestStopException
from app.ukk_runner.utils.ssh import SSHClient
from app.ukk_runner.utils.compare import compare


class TestRunner:

    def __init__(self, data, nodes):
        self.data = data
        self.nodes = nodes
        self.nodes_ssh = []
        self.pve_ssh = None
        self.ubuntu_ssh = None
        self.score = ScoreManager()

    def run(self):
        yield {"event": "start"}

        for node in self.nodes:
            ssh_client = SSHClient(node["host"], node["user"], node["password"]).connect()
            self.nodes_ssh.append(ssh_client)

        yield from self.run_proxmox()
        yield from self.run_ubuntu()
        yield from self.run_php()
        yield from self.run_web()
        yield from self.run_mysql()
        yield from self.run_wordpress()
        yield from self.run_dns()

        yield {
            "event": "finished",
            "summary": self.score.summary()
        }

    def run_proxmox(self):
        scanner = VMChecker(self.nodes_ssh)
        vm = scanner.find_vm(self.data["vm_proxmox"]["inputs"]["name"])

        if not vm:
            result = format_result(
                "proxmox", "PVE-01", "Validate VM Exists",
                {"status": False, "message": "VM not found"}, score=10
            )
            self.score.add(result)
            yield result
            raise TestStopException("Proxmox VM not found. Cannot continue tests.")

        result = format_result(
            "proxmox", "PVE-01", "Validate VM Exists", {"status": True}
        )
        self.score.add(result)
        yield result

        node_ssh_connection = vm["node_ssh_connection"]
        resources = scanner.check_resources(node_ssh_connection, vm["vmid"])
        results = compare(resources, self.data["vm_proxmox"]["expected"]["resources"])

        for key, value in results.items():
            result = format_result(
                "proxmox", f"PVE-RES-{key.upper()}", f"Validate Resource {key}",
                {"status": value["status"], "message": f"expected={value['expected']} actual={value['actual']}"},
                score=5
            )
            self.score.add(result)
            yield result

        status = scanner.check_status(node_ssh_connection, vm["vmid"])
        expected = (self.data["vm_proxmox"]["expected"].get("vm_status") or "running").strip()
        status_ok = (status or "").strip().lower() == expected.lower()
        result = format_result(
            "proxmox", "PVE-02", "Validate VM Running",
            {
                "status": status_ok,
                "expected": expected,
                "actual": status or "unknown",
                "message": None if status_ok else f"expected vm_status={expected!r}, actual={status!r}",
            }
        )
        self.score.add(result)
        yield result

        node_ssh_connection.close()

        try:
            self.pve_ssh = SSHClient(
                self.data["vm_proxmox"]["inputs"]["host"],
                self.data["vm_proxmox"]["inputs"]["user"],
                self.data["vm_proxmox"]["inputs"]["password"]
            ).connect()
            access_status = True
            ssh_error = None
        except Exception as e:
            access_status = False
            ssh_error = str(e) or type(e).__name__

        result = format_result(
            "proxmox", "PVE-03", "Validate Proxmox SSH Access",
            {"status": access_status, "message": ssh_error}
        )
        self.score.add(result)
        yield result
        if not access_status:
            raise TestStopException(
                f"Proxmox SSH Access gagal. Test dihentikan. Error: {ssh_error}"
            )

    def run_ubuntu(self):
        scanner = VMChecker([self.pve_ssh])
        vm = scanner.find_vm(self.data["vm_ubuntu"]["inputs"]["name"])

        if not vm:
            result = format_result(
                "ubuntu", "UBU-01", "Validate Ubuntu VM Exists",
                {"status": False}, score=10
            )
            self.score.add(result)
            yield result
            raise TestStopException("Ubuntu VM not found. Cannot continue tests.")

        result = format_result(
            "ubuntu", "UBU-01", "Validate Ubuntu VM Exists", {"status": True}
        )
        self.score.add(result)
        yield result

        resources = scanner.check_resources(self.pve_ssh, vm["vmid"])
        results = compare(resources, self.data["vm_ubuntu"]["expected"]["resources"])

        for key, value in results.items():
            result = format_result(
                "ubuntu", f"UBU-RES-{key.upper()}", f"Validate Ubuntu Resource {key}",
                {"status": value["status"], "message": f"expected={value['expected']} actual={value['actual']}"},
                score=5
            )
            self.score.add(result)
            yield result

        status = scanner.check_status(self.pve_ssh, vm["vmid"])
        result = format_result(
            "ubuntu", "UBU-02", "Validate Ubuntu Running",
            {"status": status == "running"}
        )
        self.score.add(result)
        yield result

        self.pve_ssh.close()

        try:
            self.ubuntu_ssh = SSHClient(
                self.data["vm_ubuntu"]["inputs"]["host"],
                self.data["vm_ubuntu"]["inputs"]["user"],
                self.data["vm_ubuntu"]["inputs"]["password"]
            ).connect()
            access_status = True
            ssh_error = None
        except Exception as e:
            access_status = False
            ssh_error = str(e) or type(e).__name__

        result = format_result(
            "ubuntu", "UBU-03", "Validate Ubuntu SSH Access",
            {"status": access_status, "message": ssh_error}
        )
        self.score.add(result)
        yield result
        if not access_status:
            raise TestStopException(
                f"Ubuntu SSH Access gagal. Test dihentikan. Error: {ssh_error}"
            )

    def run_php(self):
        checker = PHPChecker(self.ubuntu_ssh)
        raw = checker.check_php_binary("php")
        result = format_result("php", "PHP-01", "Validate PHP Binary", raw)
        self.score.add(result)
        yield result

        raw = checker.check_php_modules(self.data["php"]["expected"]["modules"])
        result = format_result("php", "PHP-02", "Validate PHP Modules", raw)
        self.score.add(result)
        yield result

    def run_web(self):
        checker = WebServerChecker(self.ubuntu_ssh)
        for code, name, method in [
            ("WEB-01", "Validate Nginx Binary", checker.check_nginx_binary),
            ("WEB-02", "Validate Nginx Service", checker.check_nginx_service),
            ("WEB-03", "Validate Nginx Config Syntax", checker.check_nginx_config_syntax),
        ]:
            raw = method()
            result = format_result("web", code, name, raw)
            self.score.add(result)
            yield result

    def run_mysql(self):
        checker = MySQLChecker(self.ubuntu_ssh)
        for code, name, method in [
            ("SQL-01", "Validate MySQL Binary", checker.check_mysql_binary),
            ("SQL-02", "Validate MySQL Service", checker.check_mysql_service),
        ]:
            raw = method()
            result = format_result("mysql", code, name, raw)
            self.score.add(result)
            yield result

        raw = checker.check_database_exists(
            db_name=self.data["mysql"]["inputs"]["db_name"], mysql_user="root"
        )
        result = format_result("mysql", "SQL-03", "Validate Database Exists", raw)
        self.score.add(result)
        yield result

        raw = checker.check_database_user_exists(
            db_user=self.data["mysql"]["inputs"]["db_user"], mysql_user="root"
        )
        result = format_result("mysql", "SQL-04", "Validate DB User Exists", raw)
        self.score.add(result)
        yield result

        raw = checker.check_wordpress_db_connection(
            db_name=self.data["mysql"]["inputs"]["db_name"],
            db_user=self.data["mysql"]["inputs"]["db_user"],
            db_password=self.data["mysql"]["inputs"]["db_password"],
        )
        result = format_result("mysql", "SQL-05", "Validate DB Connection", raw, score=10)
        self.score.add(result)
        yield result

    def run_wordpress(self):
        checker = WordPressChecker(self.data["wordpress"]["inputs"])
        raw = checker.check_wordpress_login()
        result = format_result(
            "wordpress", "WP-01", "Validate WordPress Login", raw, score=15
        )
        self.score.add(result)
        yield result

    def run_dns(self):
        checker = DNSChecker(self.ubuntu_ssh)
        for code, name, method in [
            ("DNS-01", "Validate BIND Binary", checker.check_bind_binary),
            ("DNS-02", "Validate DNS Service", checker.check_bind_service),
        ]:
            raw = method()
            result = format_result("dns", code, name, raw)
            self.score.add(result)
            yield result

        raw = checker.check_forward_dns(
            domain=self.data["dns"]["expected"]["domain"],
            expected_ip=self.data["dns"]["expected"]["ip"]
        )
        result = format_result("dns", "DNS-03", "Validate Forward DNS", raw)
        self.score.add(result)
        yield result

        raw = checker.check_reverse_dns(
            ip_address=self.data["dns"]["expected"]["ip"],
            expected_domain=self.data["dns"]["expected"]["domain"]
        )
        result = format_result("dns", "DNS-04", "Validate Reverse DNS", raw)
        self.score.add(result)
        yield result
