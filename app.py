import os
import sqlite3
import secrets
import string
import subprocess
import threading
import time

from flask import Flask, request, redirect, session, abort, jsonify
from flask_sock import Sock
from websocket import create_connection

app = Flask(__name__)
sock = Sock(app)

# ==============================
# CONFIG
# ==============================

MASTER_KEY = "maha7788"

DB = "/data/users.db"

app.secret_key = secrets.token_hex(64)

# ==============================
# DATABASE
# ==============================

os.makedirs("/data", exist_ok=True)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            endpoint TEXT UNIQUE NOT NULL
        )
    """)

    con.commit()
    con.close()


def random_endpoint():
    chars = string.ascii_lowercase + string.digits

    while True:
        value = "".join(
            secrets.choice(chars)
            for _ in range(24)
        )

        con = db()

        exists = con.execute(
            "SELECT 1 FROM users WHERE endpoint=?",
            (value,)
        ).fetchone()

        con.close()

        if not exists:
            return value


# ==============================
# FIREFOX START
# ==============================

def start_firefox():

    subprocess.Popen(
        [
            "Xvfb",
            ":99",
            "-screen",
            "0",
            "1280x800x24",
            "-ac"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)

    subprocess.Popen(
        [
            "fluxbox"
        ],
        env={
            **os.environ,
            "DISPLAY": ":99"
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(1)

    subprocess.Popen(
        [
            "x11vnc",
            "-display",
            ":99",
            "-forever",
            "-shared",
            "-nopw",
            "-rfbport",
            "5900",
            "-localhost"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)

    subprocess.Popen(
        [
            "websockify",
            "--web=/usr/share/novnc/",
            "6080",
            "localhost:5900"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    time.sleep(2)

    subprocess.Popen(
        [
            "firefox-esr",
            "--no-remote",
            "--profile",
            "/firefox-profile",
            "about:blank"
        ],
        env={
            **os.environ,
            "DISPLAY": ":99"
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


# ==============================
# HOME
# ==============================

@app.route("/")
def home():

    if session.get("endpoint"):
        return redirect(
            "/firefox/" + session["endpoint"]
        )

    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Firefox Login</title>

<style>
body{
    margin:0;
    min-height:100vh;
    background:#101010;
    color:white;
    font-family:Arial;
    display:flex;
    align-items:center;
    justify-content:center;
}

.box{
    width:330px;
    max-width:90%;
    background:#1c1c1c;
    padding:25px;
    border-radius:15px;
}

h2{
    text-align:center;
}

input{
    width:100%;
    box-sizing:border-box;
    padding:13px;
    margin:7px 0;
    border:0;
    border-radius:8px;
    background:#292929;
    color:white;
}

button{
    width:100%;
    padding:13px;
    margin-top:10px;
    border:0;
    border-radius:8px;
    background:#5865f2;
    color:white;
    font-weight:bold;
}
</style>
</head>

<body>

<div class="box">

<h2>Firefox Login</h2>

<form method="POST" action="/login">

<input
 name="username"
 placeholder="Username"
 required
>

<input
 name="password"
 type="password"
 placeholder="Password"
 required
>

<button>Login</button>

</form>

</div>

</body>
</html>
"""


# ==============================
# LOGIN
# ==============================

@app.route("/login", methods=["POST"])
def login():

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    con = db()

    user = con.execute(
        """
        SELECT * FROM users
        WHERE username=? AND password=?
        """,
        (username, password)
    ).fetchone()

    con.close()

    if not user:
        return """
        <h3>Invalid username or password</h3>
        <a href="/">Back</a>
        """, 401

    session.clear()

    session["username"] = username
    session["endpoint"] = user["endpoint"]

    return redirect(
        "/firefox/" + user["endpoint"]
    )


# ==============================
# ADD USER
# ==============================

@app.route("/adduser")
def adduser():

    key = request.args.get("key")
    username = request.args.get("username", "").strip()
    password = request.args.get("password", "")

    if key != MASTER_KEY:
        return jsonify({
            "status": "error",
            "message": "Invalid key"
        }), 403

    if not username or not password:
        return jsonify({
            "status": "error",
            "message": "username and password required"
        }), 400

    con = db()

    exists = con.execute(
        "SELECT 1 FROM users WHERE username=?",
        (username,)
    ).fetchone()

    if exists:
        con.close()

        return jsonify({
            "status": "error",
            "message": "Username already exists"
        }), 409

    endpoint = random_endpoint()

    con.execute(
        """
        INSERT INTO users
        (username,password,endpoint)
        VALUES (?,?,?)
        """,
        (username, password, endpoint)
    )

    con.commit()
    con.close()

    base = request.host_url.rstrip("/")

    return jsonify({
        "status": "success",
        "username": username,
        "endpoint": endpoint,
        "url": f"{base}/firefox/{endpoint}"
    })


# ==============================
# DELETE USER
# ==============================

@app.route("/delete")
def delete():

    key = request.args.get("key")
    username = request.args.get("username", "").strip()
    password = request.args.get("password", "")

    if key != MASTER_KEY:
        return jsonify({
            "status": "error",
            "message": "Invalid key"
        }), 403

    con = db()

    user = con.execute(
        """
        SELECT * FROM users
        WHERE username=? AND password=?
        """,
        (username, password)
    ).fetchone()

    if not user:
        con.close()

        return jsonify({
            "status": "error",
            "message": "User not found"
        }), 404

    con.execute(
        "DELETE FROM users WHERE username=?",
        (username,)
    )

    con.commit()
    con.close()

    return jsonify({
        "status": "success",
        "message": "User deleted"
    })


# ==============================
# FIREFOX PAGE
# ==============================

@app.route("/firefox/<endpoint>")
def firefox(endpoint):

    con = db()

    user = con.execute(
        "SELECT * FROM users WHERE endpoint=?",
        (endpoint,)
    ).fetchone()

    con.close()

    if not user:
        abort(404)

    if session.get("endpoint") != endpoint:
        return redirect("/")

    # noVNC opens inside same authenticated endpoint
    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Firefox</title>

<style>
html,body {{
    margin:0;
    width:100%;
    height:100%;
    overflow:hidden;
    background:#000;
}}

iframe {{
    width:100%;
    height:100%;
    border:0;
}}
</style>
</head>

<body>

<iframe
src="/firefox/{endpoint}/novnc/vnc.html?autoconnect=true&resize=scale&path=firefox/{endpoint}/websockify"
></iframe>

</body>
</html>
"""


# ==============================
# NOVNC STATIC FILES
# ==============================

@app.route("/firefox/<endpoint>/novnc/<path:path>")
def novnc(endpoint, path):

    con = db()

    user = con.execute(
        "SELECT 1 FROM users WHERE endpoint=?",
        (endpoint,)
    ).fetchone()

    con.close()

    if not user:
        abort(404)

    if session.get("endpoint") != endpoint:
        return redirect("/")

    file_path = os.path.join(
        "/usr/share/novnc",
        path
    )

    if not os.path.isfile(file_path):
        abort(404)

    from flask import send_file

    return send_file(file_path)


# ==============================
# WEBSOCKET PROXY
# ==============================

@sock.route("/firefox/<endpoint>/websockify")
def websocket_proxy(ws, endpoint):

    con = db()

    user = con.execute(
        "SELECT 1 FROM users WHERE endpoint=?",
        (endpoint,)
    ).fetchone()

    con.close()

    if not user:
        ws.close()
        return

    try:

        remote = create_connection(
            "ws://127.0.0.1:6080/websockify",
            timeout=10
        )

        def browser_to_vnc():

            try:
                while True:

                    data = ws.receive()

                    if data is None:
                        break

                    if isinstance(data, str):
                        remote.send(data)
                    else:
                        remote.send_binary(data)

            except Exception:
                pass

        thread = threading.Thread(
            target=browser_to_vnc,
            daemon=True
        )

        thread.start()

        while True:

            data = remote.recv()

            if data is None:
                break

            ws.send(data)

    except Exception:
        pass

    finally:

        try:
            remote.close()
        except:
            pass

        try:
            ws.close()
        except:
            pass


# ==============================
# LOGOUT
# ==============================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ==============================
# START
# ==============================

init_db()

start_firefox()

port = int(os.environ.get("PORT", "8080"))

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=port
    )
