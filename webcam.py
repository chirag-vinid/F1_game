from flask import Flask, render_template_string, jsonify, send_from_directory
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import cv2
import os

LEADERBOARD_FILE = "leaderboard.txt"
IMAGES_DIR = "images"

app = Flask(__name__)

leaderboard_times = []
last_update_time = 0
last_new_rank = None  # Rank of the newest time added

# Ensure images folder exists
os.makedirs(IMAGES_DIR, exist_ok=True)


def capture_webcam_image(filename):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam!")
        return
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(filename, frame)
        print(f"Webcam image saved to {filename}")
    else:
        print("Failed to capture webcam image.")
    cap.release()


class LeaderboardHandler(FileSystemEventHandler):
    def on_modified(self, event):
        global leaderboard_times, last_update_time, last_new_rank
        if event.src_path.endswith(LEADERBOARD_FILE):
            print(f"{LEADERBOARD_FILE} changed, reloading times...")
            try:
                with open(LEADERBOARD_FILE, "r") as f:
                    lines = f.readlines()
                times = []
                for line in lines:
                    parts = line.strip().split(",", 1)
                    if parts:
                        try:
                            time_ms = float(parts[0])
                            times.append(time_ms)
                        except Exception:
                            pass
                times = sorted(times)[:10]

                # Find newly added times compared to previous
                new_times = [t for t in times if t not in leaderboard_times]

                if new_times:
                    newest_time = min(new_times)
                    rank = times.index(newest_time) + 1
                    # Save webcam image as rank.jpg in images folder
                    capture_webcam_image(os.path.join(IMAGES_DIR, f"{rank}.jpg"))
                    last_new_rank = rank
                else:
                    last_new_rank = None

                leaderboard_times[:] = times
                last_update_time = time.time()
            except Exception as e:
                print("Error reading leaderboard:", e)


@app.route("/")
def index():
    html = """
    <!doctype html>
    <html>
    <head>
        <title>Leaderboard With Webcam</title>
        <style>
            body { background: #111; color: #eee; font-family: Arial, sans-serif; text-align: center; padding: 30px; }
            h1 { color: #f90; margin-bottom: 20px; }
            ul { list-style: none; padding: 0; max-width: 300px; margin: auto; }
            li { font-size: 1.8rem; background: #222; margin: 5px 0; padding: 12px; border-radius: 8px; color: #0f0; font-weight: bold; }
            .loading { font-style: italic; color: #888; }
            img { max-width: 300px; margin-top: 20px; border-radius: 10px; }
        </style>
        <script>
            async function fetchTimes() {
                try {
                    const res = await fetch('/times');
                    if (res.ok) {
                        const data = await res.json();
                        const list = document.getElementById('timesList');
                        if (data.times.length === 0) {
                            list.innerHTML = '<li class="loading">No times recorded yet</li>';
                        } else {
                            list.innerHTML = data.times.map((ms, i) => `<li>#${i+1}: ${ms.toFixed(3)} ms</li>`).join('');
                        }
                        document.getElementById('lastUpdated').textContent = new Date(data.timestamp * 1000).toLocaleString();

                        const image = document.getElementById('webcamImage');
                        if(data.rank){
                            image.style.display = 'block';
                            image.src = '/images/' + data.rank + '.jpg?rand=' + new Date().getTime();
                        } else {
                            image.style.display = 'none';
                        }
                    }
                } catch(err) {
                    console.error("Error fetching times:", err);
                }
            }
            setInterval(fetchTimes, 3000);
            window.onload = fetchTimes;
        </script>
    </head>
    <body>
        <h1>Top 10 Reaction Times (ms)</h1>
        <ul id="timesList"><li class="loading">Loading...</li></ul>
        <p>Last updated: <span id="lastUpdated">Never</span></p>
        <img id="webcamImage" src="" alt="Webcam capture image" style="display:none" />
    </body>
    </html>
    """
    return html


@app.route("/times")
def get_times():
    global leaderboard_times, last_update_time, last_new_rank
    return jsonify({
        "times": leaderboard_times,
        "timestamp": last_update_time,
        "rank": last_new_rank
    })


@app.route('/images/<filename>')
def serve_image(filename):
    allowed = [f"{i}.jpg" for i in range(1, 11)]
    image_path = os.path.join(IMAGES_DIR, filename)
    if filename in allowed and os.path.exists(image_path):
        return send_from_directory(IMAGES_DIR, filename)
    return "", 404



def start_watcher():
    event_handler = LeaderboardHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    print("Started watchdog observer for leaderboard.txt")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    # Initial load to populate data
    if os.path.exists(LEADERBOARD_FILE):
        LeaderboardHandler().on_modified(type('', (), {'src_path': LEADERBOARD_FILE})())

    watcher_thread = threading.Thread(target=start_watcher, daemon=True)
    watcher_thread.start()

    app.run(host="0.0.0.0", port=5051, debug=False)
