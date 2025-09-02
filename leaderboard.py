from flask import Flask, render_template_string, jsonify
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os

LEADERBOARD_FILE = "leaderboard.txt"

app = Flask(__name__)

leaderboard_data = []
last_update_time = 0

class LeaderboardHandler(FileSystemEventHandler):
    def on_modified(self, event):
        global leaderboard_data, last_update_time
        if event.src_path.endswith(LEADERBOARD_FILE):
            print(f"{LEADERBOARD_FILE} changed, reloading data...")
            try:
                with open(LEADERBOARD_FILE, "r") as f:
                    lines = f.readlines()
                new_leaderboard = []
                for line in lines:
                    parts = line.strip().split(",", 3)
                    if len(parts) == 4:
                        try:
                            time_ms = float(parts[0])
                            name = parts[1]
                            roll = parts[2]
                            timestamp = parts[3]
                            new_leaderboard.append({'time': time_ms, 'name': name, 'roll': roll, 'timestamp': timestamp})
                        except Exception as e:
                            print(f"Error processing line: {line}. Error: {e}")
                            pass
                
                new_leaderboard.sort(key=lambda x: x['time'])
                leaderboard_data[:] = new_leaderboard[:10]
                last_update_time = time.time()
            except Exception as e:
                print("Error reading leaderboard:", e)

@app.route("/")
def index():
    html = """
    <!doctype html>
    <html>
    <head>
        <title>F1 Reaction Leaderboard</title>
        <style>
            body { background: #111; color: #eee; font-family: Arial, sans-serif; text-align: center; padding: 30px; }
            h1 { color: #f90; margin-bottom: 20px; }
            .leaderboard-table { width: 80%; margin: auto; border-collapse: collapse; }
            .leaderboard-table th, .leaderboard-table td { padding: 10px; border-bottom: 1px solid #444; }
            .leaderboard-table th { background: #222; }
            p.update-time { font-style: italic; color: #888; }
        </style>
        <script>
            async function fetchData() {
                try {
                    const res = await fetch('/data');
                    if (res.ok) {
                        const data = await res.json();
                        const tableBody = document.getElementById('leaderboardTableBody');
                        
                        tableBody.innerHTML = '';

                        if (data.leaderboard.length === 0) {
                            tableBody.innerHTML = '<tr><td colspan="4">No times recorded yet</td></tr>';
                        } else {
                            data.leaderboard.forEach((entry, i) => {
                                tableBody.innerHTML += `
                                    <tr>
                                        <td>#${i+1}</td>
                                        <td>${(entry.time/1000).toFixed(3)} ms</td>
                                        <td>${entry.name}</td>
                                        <td>${entry.roll}</td>
                                    </tr>`;
                            });
                        }
                    }
                } catch(err) {
                    console.error("Error fetching data:", err);
                }
            }
            setInterval(fetchData, 3000);
            window.onload = fetchData;
        </script>
    </head>
    <body>
        <h1>F1 Reaction Leaderboard</h1>
        <table class="leaderboard-table">
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Time (ms)</th>
                    <th>Name</th>
                    <th>Roll No.</th>
                </tr>
            </thead>
            <tbody id="leaderboardTableBody">
            </tbody>
        </table>
        <p class="update-time">This page updates automatically.</p>
    </body>
    </html>
    """
    return html

@app.route("/data")
def get_data():
    global leaderboard_data, last_update_time
    return jsonify({"leaderboard": leaderboard_data})

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
    if os.path.exists(LEADERBOARD_FILE):
        LeaderboardHandler().on_modified(type('', (), {'src_path': LEADERBOARD_FILE})())
    
    watcher_thread = threading.Thread(target=start_watcher, daemon=True)
    watcher_thread.start()

    app.run(host="0.0.0.0", port=5051, debug=False)