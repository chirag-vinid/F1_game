from flask import Flask, render_template_string, jsonify, send_from_directory
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os

LEADERBOARD_FILE = "leaderboard.txt"
IMAGES_DIR = "images"

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
                    parts = line.strip().split(",", 4)
                    if len(parts) == 5:
                        try:
                            time_us = float(parts[0])
                            name = parts[1]
                            roll = parts[2]
                            timestamp = parts[3]
                            image_file = parts[4]
                            new_leaderboard.append({'time': time_us, 'name': name, 'roll': roll, 'timestamp': timestamp, 'image': image_file})
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
            .leaderboard-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; }
            .leaderboard-table { width: 100%; border-collapse: collapse; }
            .leaderboard-table th, .leaderboard-table td { padding: 10px; border-bottom: 1px solid #444; }
            .leaderboard-table th { background: #222; }
            .player-cards { display: flex; flex-direction: column; gap: 20px; }
            .player-card { background: #222; padding: 15px; border-radius: 10px; display: flex; align-items: center; gap: 15px; }
            .player-card img { width: 100px; height: 100px; border-radius: 50%; object-fit: cover; border: 3px solid #f90; }
            .player-info { text-align: left; }
            .player-info h3 { margin: 0; font-size: 1.2em; color: #0f0; }
            .player-info p { margin: 2px 0; font-size: 0.9em; }
        </style>
        <script>
            async function fetchData() {
                try {
                    const res = await fetch('/data');
                    if (res.ok) {
                        const data = await res.json();
                        const tableBody = document.getElementById('leaderboardTableBody');
                        const playerCards = document.getElementById('playerCards');
                        
                        // FIX: Separate table and card rendering for stability
                        tableBody.innerHTML = '';
                        playerCards.innerHTML = '';

                        if (data.leaderboard.length === 0) {
                            tableBody.innerHTML = '<tr><td colspan="4">No times recorded yet</td></tr>';
                            playerCards.innerHTML = '<p>No photos yet. Be the first!</p>';
                        } else {
                            // Render the table first (synchronously)
                            data.leaderboard.forEach((entry, i) => {
                                tableBody.innerHTML += `
                                    <tr>
                                        <td>#${i+1}</td>
                                        <td>${(entry.time / 1000).toFixed(3)} s</td>
                                        <td>${entry.name}</td>
                                        <td>${entry.roll}</td>
                                    </tr>`;
                            });

                            // Then, render the player cards (asynchronously)
                            const cardPromises = data.leaderboard.map((entry, i) => {
                                return new Promise(resolve => {
                                    const cardDiv = document.createElement('div');
                                    cardDiv.className = 'player-card';

                                    const infoDiv = document.createElement('div');
                                    infoDiv.className = 'player-info';
                                    infoDiv.innerHTML = `
                                        <h3>${entry.name}</h3>
                                        <p>Rank #${i+1}</p>
                                        <p>Time: ${(entry.time / 1000).toFixed(3)} s</p>`;
                                    cardDiv.appendChild(infoDiv);

                                    if (entry.image !== "N/A" && entry.image !== "") {
                                        const img = new Image();
                                        img.src = '/images/' + entry.image + '?t=' + new Date().getTime();
                                        img.alt = "Player photo for rank #" + (i + 1);
                                        
                                        img.onload = () => {
                                            cardDiv.prepend(img);
                                            resolve(cardDiv);
                                        };
                                        img.onerror = () => {
                                            const placeholder = document.createElement('img');
                                            placeholder.src = '/images/no_photo.png';
                                            placeholder.alt = "No photo available";
                                            placeholder.className = 'player-photo-placeholder';
                                            cardDiv.prepend(placeholder);
                                            resolve(cardDiv);
                                        };
                                    } else {
                                        const placeholder = document.createElement('img');
                                        placeholder.src = '/images/no_photo.png';
                                        placeholder.alt = "No photo available";
                                        placeholder.className = 'player-photo-placeholder';
                                        cardDiv.prepend(placeholder);
                                        resolve(cardDiv);
                                    }
                                });
                            });

                            Promise.all(cardPromises).then(cards => {
                                cards.forEach(card => playerCards.appendChild(card));
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
        <div class="leaderboard-grid">
            <div>
                <h2>Top Times</h2>
                <table class="leaderboard-table">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Time (s)</th>
                            <th>Name</th>
                            <th>Roll No.</th>
                        </tr>
                    </thead>
                    <tbody id="leaderboardTableBody">
                    </tbody>
                </table>
            </div>
            <div>
                <h2>Top Players</h2>
                <div class="player-cards" id="playerCards">
                    <p>Loading photos...</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

@app.route("/data")
def get_data():
    global leaderboard_data, last_update_time
    return jsonify({"leaderboard": leaderboard_data})

@app.route('/images/<filename>')
def serve_image(filename):
    image_path = os.path.join(IMAGES_DIR, filename)
    if os.path.exists(image_path):
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
    if os.path.exists(LEADERBOARD_FILE):
        LeaderboardHandler().on_modified(type('', (), {'src_path': LEADERBOARD_FILE})())
    
    watcher_thread = threading.Thread(target=start_watcher, daemon=True)
    watcher_thread.start()

    app.run(host="0.0.0.0", port=5051, debug=False)