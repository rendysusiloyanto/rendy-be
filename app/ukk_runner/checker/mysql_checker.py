from app.ukk_runner.utils.ssh import SSHClient


class MySQLChecker:
    def __init__(self, vm_ssh_connection):
        self.vm_ssh_connection = vm_ssh_connection

    def _build_mysql_command(self, query, mysql_user="root", mysql_password=None):
        if mysql_password is None:
            return f"sudo -S mysql -u {mysql_user} -e \"{query}\""
        elif mysql_password == "":
            return f"mysql -u {mysql_user} -e \"{query}\""
        return f"mysql -u {mysql_user} -p\"{mysql_password}\" -e \"{query}\""

    def check_mysql_binary(self):
        try:
            res = self.vm_ssh_connection.run("which mysql")
            found = bool(res.get_output().strip())
            return {"step": "5.A", "status": found, "path": res.get_output().strip() if found else None, "message": None if found else "MySQL binary not found"}
        except Exception as e:
            return {"step": "5.A", "status": False, "path": None, "message": str(e)}

    def check_mysql_service(self):
        try:
            res = self.vm_ssh_connection.run("systemctl is-active mysql")
            active = res.get_output().strip() == "active"
            return {"step": "5.B", "status": active, "value": active, "message": None if active else "MySQL service not running"}
        except Exception as e:
            return {"step": "5.B", "status": False, "value": False, "message": str(e)}

    def check_database_exists(self, db_name, mysql_user="root", mysql_password=None):
        try:
            cmd = self._build_mysql_command(f"SHOW DATABASES LIKE '{db_name}';", mysql_user, mysql_password)
            res = self.vm_ssh_connection.run(cmd, use_sudo=(mysql_password is None))
            exists = db_name in res.get_output()
            return {"step": "5.C", "status": exists, "database": db_name, "message": None if exists else f"DB '{db_name}' not found"}
        except Exception as e:
            return {"step": "5.C", "status": False, "database": db_name, "message": str(e)}

    def check_database_user_exists(self, db_user, mysql_user="root", mysql_password=None):
        try:
            cmd = self._build_mysql_command(f"SELECT User FROM mysql.user WHERE User = '{db_user}';", mysql_user, mysql_password)
            res = self.vm_ssh_connection.run(cmd, use_sudo=(mysql_password is None))
            exists = db_user in res.get_output()
            return {"step": "5.D", "status": exists, "db_user": db_user, "message": None if exists else f"User '{db_user}' not found"}
        except Exception as e:
            return {"step": "5.D", "status": False, "db_user": db_user, "message": str(e)}

    def check_wordpress_db_connection(self, db_name, db_user, db_password):
        try:
            cmd = f'mysql -u {db_user} -p"{db_password}" -e "USE {db_name};"'
            res = self.vm_ssh_connection.run(cmd)
            success = res.get_status() == 0
            return {"step": "5.E", "status": success, "message": None if success else res.get_error().strip()}
        except Exception as e:
            return {"step": "5.E", "status": False, "message": str(e)}
