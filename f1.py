import serial
import json
from flask import Flask, render_template_string, jsonify
import threading
import time
import datetime


PORT = "COM10"
BAUD = 9600
ser = serial.Serial(PORT, BAUD)

app = Flask(__name__)

leaderboard = []
current_stage = {"type": "idle", "value": None}
time_shown_until = 0  # timestamp until 'time' is shown


HTML = """
<!doctype html>
<html>
<head>
    <title>F1 Reaction Timer</title>
    <style>
        body { font-family: Arial, sans-serif; background: #111; color: #eee; margin:0; display:flex; align-items:center; justify-content:center; height:100vh; }
        .big    { font-size: 120px; color:#f90; }
        .time   { font-size: 80px; color:#0f0; }
        .leaderboard { width: 60%; margin:auto; background:#222; padding:20px; border-radius:10px; }
        h1      { color:#f90; }
        table   { width:100%; border-collapse:collapse; margin-top:20px; }
        th,td   { padding:10px; border-bottom:1px solid #444; text-align:center; }
    </style>
    <script>
        async function refreshStage(){
            try {
                let r = await fetch("/stage");
                if (!r.ok) {
                    console.error("Network response was not ok");
                    return;
                }
                let data = await r.json();
                let content = document.getElementById("content");

                console.log("Stage data received:", data);

                if(data.type === "countdown"){
                    content.innerHTML = `<div class='big'>${data.value}</div>`;
                }
                else if(data.type === "time"){
                    content.innerHTML = `<div class='time'>${data.value.toFixed(3)}ms</div>`;
                }
                else if(data.type === "leaderboard"){
                    if (!data.leaderboard || data.leaderboard.length === 0) {
                        content.innerHTML = "<div class='leaderboard'><h1>No leaderboard data yet</h1></div>";
                        return;
                    }
                    let html = `<div class='leaderboard'>
                        <h1>🏆 Fastest Reaction Leaderboard</h1>
                        <table>
                            <tr><th>Rank</th><th>Time (s)</th><th>Timestamp</th></tr>`;

                    data.leaderboard.forEach((t,i)=>{
                        // Defensive checks for data format
                        let time = (t[0] !== undefined) ? t[0].toFixed(3) : "N/A";
                        let timestamp = t[1] || "N/A";
                        html += `<tr><td>${i+1}</td><td>${time}</td><td>${timestamp}</td></tr>`;
                    });
                    html += "</table></div>";
                    content.innerHTML = html;
                }
                else {
                    // Unknown / idle stage
                    content.innerHTML = "<div>Waiting for reaction timer to start...</div>";
                }
            } catch (err) {
                console.error("Error refreshing stage:", err);
            }
        }
        setInterval(refreshStage, 1000);
        window.onload = refreshStage;
    </script>
</head>
<body>
    <div id="content">Loading...</div>
</body>
</html>

"""

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/stage")
def get_stage():
    global current_stage, time_shown_until
    now = time.time()
    # Auto change from 'time' to 'leaderboard' after 2 seconds
    if current_stage["type"] == "time" and now >= time_shown_until:
        current_stage_local = {
            "type": "leaderboard",
            "value": None,
            "leaderboard": leaderboard
        }
    else:
        current_stage_local = current_stage

    # Convert tuples to lists for JSON
    if current_stage_local.get("type") == "leaderboard":
        lb = current_stage_local.get("leaderboard", [])
        current_stage_local["leaderboard"] = [list(t) for t in lb]

    return jsonify(current_stage_local)


def read_serial():
    global current_stage, leaderboard, time_shown_until
    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            if line in ["1", "2", "3"]:
                current_stage = {"type": "countdown", "value": int(line)}

            elif line.startswith("{") and line.endswith("}"):
                data = json.loads(line)
                if "time_us" in data:
                    time_val = float(data["time_us"]) / 1000.0
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Load existing leaderboard from file to get current highest time
                    existing_leaderboard = []
                    try:
                        with open("leaderboard.txt", "r") as f:
                            for row in f:
                                if not row.strip():
                                    continue
                                parts = row.strip().split(",", 1)
                                if len(parts) == 2:
                                    t_val = float(parts[0])
                                    t_stamp = parts[1]
                                    existing_leaderboard.append((t_val, t_stamp))
                    except FileNotFoundError:
                        existing_leaderboard = []

                    # Determine if new time qualifies (faster than max or leaderboard empty)
                    if len(existing_leaderboard) < 10 or time_val < max(t[0] for t in existing_leaderboard):
                        existing_leaderboard.append((time_val, timestamp))
                        # Sort by time ascending and keep top 10
                        existing_leaderboard = sorted(existing_leaderboard, key=lambda x: x[0])[:10]
                        leaderboard[:] = existing_leaderboard  # Update in-memory leaderboard

                        # Write updated leaderboard back to file
                        with open("leaderboard.txt", "w") as f:
                            for t in existing_leaderboard:
                                f.write(f"{t[0]},{t[1]}\n")

                    current_stage = {"type": "time", "value": time_val}
                    time_shown_until = time.time() + 2  # Display time for 2 seconds then switch

            else:
                pass

        except (ValueError, json.JSONDecodeError):
            continue


if __name__ == "__main__":
    open("leaderboard.txt", "w").close()  # clear file at start
    threading.Thread(target=read_serial, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
