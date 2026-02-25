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
            out, err = res.get_output(), res.get_error()
            found = bool(out.strip())
            return {
                "step": "5.A", "status": found,
                "path": out.strip() if found else None,
                "message": None if found else "MySQL binary not found",
                "command_output": (out + "\n" + err).strip() or None,
            }
        except Exception as e:
            return {"step": "5.A", "status": False, "path": None, "message": str(e)}

    def check_mysql_service(self):
        try:
            res = self.vm_ssh_connection.run("systemctl is-active mysql")
            active = res.get_output().strip() == "active"
            status_res = self.vm_ssh_connection.run("systemctl status mysql --no-pager", use_sudo=True)
            system_output = (status_res.get_output() + "\n" + status_res.get_error()).strip()
            return {
                "step": "5.B", "status": active, "value": active,
                "message": None if active else "MySQL service not running",
                "system_output": system_output,
            }
        except Exception as e:
            return {"step": "5.B", "status": False, "value": False, "message": str(e)}

    def check_database_exists(self, db_name, mysql_user="root", mysql_password=None):
        try:
            if not (db_name and str(db_name).strip()):
                return {"step": "5.C", "status": False, "database": db_name or "", "message": "DB name kosong"}
            cmd = self._build_mysql_command(f"SHOW DATABASES LIKE '{db_name}';", mysql_user, mysql_password)
            res = self.vm_ssh_connection.run(cmd, use_sudo=(mysql_password is None))
            out, err = res.get_output(), res.get_error()
            cmd_ok = res.get_status() == 0 and "command not found" not in (err or "").lower()
            exists = cmd_ok and db_name in out
            return {
                "step": "5.C", "status": exists, "database": db_name,
                "message": None if exists else (err.strip() or f"DB '{db_name}' not found"),
                "command_output": (out + "\n" + err).strip() or None,
            }
        except Exception as e:
            return {"step": "5.C", "status": False, "database": db_name, "message": str(e)}

    def check_database_user_exists(self, db_user, mysql_user="root", mysql_password=None):
        try:
            if not (db_user is not None and str(db_user).strip()):
                return {"step": "5.D", "status": False, "db_user": db_user or "", "message": "DB user kosong", "command_output": None}
            cmd = self._build_mysql_command(f"SELECT User FROM mysql.user WHERE User = '{db_user}';", mysql_user, mysql_password)
            res = self.vm_ssh_connection.run(cmd, use_sudo=(mysql_password is None))
            out, err = res.get_output(), res.get_error()
            cmd_ok = res.get_status() == 0 and "command not found" not in (err or "").lower()
            exists = cmd_ok and db_user in out
            return {
                "step": "5.D", "status": exists, "db_user": db_user,
                "message": None if exists else (err.strip() or f"User '{db_user}' not found"),
                "command_output": (out + "\n" + err).strip() or None,
            }
        except Exception as e:
            return {"step": "5.D", "status": False, "db_user": db_user, "message": str(e)}

    def check_wordpress_db_connection(self, db_name, db_user, db_password):
        try:
            cmd = f'mysql -u {db_user} -p"{db_password}" -e "USE {db_name};"'
            res = self.vm_ssh_connection.run(cmd)
            out, err = res.get_output(), res.get_error()
            success = res.get_status() == 0
            return {
                "step": "5.E", "status": success,
                "message": None if success else err.strip(),
                "command_output": (out + "\n" + err).strip() or None,
            }
        except Exception as e:
            return {"step": "5.E", "status": False, "message": str(e)}
