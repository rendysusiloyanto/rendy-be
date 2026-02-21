import requests


class WordPressChecker:
    def __init__(self, vm):
        self.url = vm["url"]
        self.username = vm["username"]
        self.password = vm["password"]

    def check_wordpress_login(self):
        try:
            session = requests.Session()
            login_url = f"{self.url}/wp-login.php"
            session.get(login_url, timeout=5)
            payload = {
                "log": self.username,
                "pwd": self.password,
                "wp-submit": "Log In",
                "redirect_to": f"{self.url}/wp-admin/",
                "testcookie": "1",
            }
            response = session.post(login_url, data=payload, timeout=5)
            success = False
            if "wp-admin" in response.url:
                success = True
            elif session.cookies.get_dict().get("wordpress_logged_in"):
                success = True
            elif "dashboard" in response.text.lower():
                success = True
            return {
                "step": "6.B Checking CMS WordPress Login",
                "status": success,
                "url": self.url,
                "username": self.username,
                "status_code": response.status_code,
                "message": None if success else "Login failed",
            }
        except Exception as e:
            return {
                "step": "6.B Checking CMS WordPress Login",
                "status": False,
                "url": self.url,
                "username": self.username,
                "status_code": getattr(e, "response", None) and getattr(e.response, "status_code", None),
                "message": str(e),
            }
