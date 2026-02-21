import paramiko


class SSHClient:
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.client = None
        self.last_output = None
        self.last_error = None
        self.last_exit_code = None

    def connect(self):
        if self.client:
            return self
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=self.host,
            username=self.username,
            password=self.password,
            allow_agent=False,
            look_for_keys=False,
            timeout=5,
        )
        return self

    def run(self, command, use_sudo=False):
        if use_sudo:
            command = f"sudo -S -p '' {command}"
        stdin, stdout, stderr = self.client.exec_command(command)
        if use_sudo:
            stdin.write(self.password + "\n")
            stdin.flush()
        self.last_output = stdout.read().decode()
        self.last_error = stderr.read().decode()
        self.last_exit_code = stdout.channel.recv_exit_status()
        return self

    def get_status(self):
        return self.last_exit_code

    def get_output(self):
        return self.last_output

    def get_error(self):
        return self.last_error

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
