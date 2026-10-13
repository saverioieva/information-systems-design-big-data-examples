import os
import signal
import threading
import time

from flask import Flask
from werkzeug.serving import make_server

app = Flask(__name__)

@app.route("/")
def index():
    return {
        "message": os.getenv("APP_MESSAGE", "Hello"),
        "uid": os.getuid(),
    }

@app.route("/slow")
def slow():
    print("work_started", flush=True)
    time.sleep(8)
    print("work_finished", flush=True)
    return {"completed": True}

if __name__ == "__main__":
    server = make_server("0.0.0.0", 5000, app, threaded=False)
    stopping = threading.Event()

    def stop(signum, frame):
        if not stopping.is_set():
            stopping.set()
            print("SIGTERM: draining current request", flush=True)
            threading.Thread(target=server.shutdown).start()

    signal.signal(signal.SIGTERM, stop)
    server.serve_forever()
    server.server_close()
    print("shutdown_complete", flush=True)
