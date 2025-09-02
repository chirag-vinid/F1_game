import serial
import json
from flask import Flask, render_template_string, jsonify, request
import threading
import time
import datetime
import os

PORT = "COM7"
BAUD = 9600
ser = None
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
except serial.SerialException as e:
    print(f"Error: Could not open serial port {PORT}. Please check the connection and port number.")
    print(e)

app = Flask(__name__)

leaderboard = []
current_stage = {"type": "landing", "value": None}
time_shown_until = 0
player_data = {"name": "Player", "roll": "N/A"}

HTML = """
<!doctype html>
<html>
<head>
    <title>F1 Reaction Timer</title>
    <style>
        body { font-family: Arial, sans-serif; background: #111; color: #eee; margin:0; display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:100vh; text-align:center;}
        .container { display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .big      { font-size: 120px; color:#f90; }
        .time     { font-size: 80px; color:#0f0; }
        .leaderboard { width: 80%; max-width: 600px; margin:20px auto; background:#222; padding:20px; border-radius:10px; }
        h1, h2    { color:#f90; text-align:center; }
        table     { width:100%; border-collapse:collapse; margin-top:20px; }
        th,td     { padding:10px; border-bottom:1px solid #444; text-align:center; }
        .landing-page, .ready-page, .game-state, .result-state { display: none; }
        .player-form { background:#333; padding:20px; border-radius:10px; margin-bottom:20px; width: 50%; max-width: 400px; }
        .player-form input, .player-form button { width: 90%; padding: 10px; margin: 10px 0; border: none; border-radius: 5px; }
        .player-form input { background: #444; color: #eee; }
        .player-form button { background: #0f0; color: #111; cursor: pointer; }
        .start-button { padding: 15px 30px; font-size: 24px; background: #f90; color: #111; border: none; border-radius: 10px; cursor: pointer; margin-top: 20px; }
        .msg { font-size: 24px; color: #fff; margin-top: 20px; }
    </style>
    <script>
        async function refreshPage(){
            try {
                let r = await fetch("/stage");
                if (!r.ok) return;
                let data = await r.json();
                
                document.getElementById('landingState').style.display = 'none';
                document.getElementById('readyPage').style.display = 'none';
                document.getElementById('gameState').style.display = 'none';
                document.getElementById('resultState').style.display = 'none';

                if(data.type === "landing" || data.type === "idle"){
                    document.getElementById('landingState').style.display = 'block';
                }
                else if(data.type === "ready"){
                    document.getElementById('readyPage').style.display = 'block';
                }
                else if(data.type === "waiting"){
                    document.getElementById('gameState').style.display = 'block';
                    document.getElementById('gameText').textContent = 'Waiting for circuit...';
                }
                else if(data.type === "countdown"){
                    document.getElementById('gameState').style.display = 'block';
                    document.getElementById('gameText').textContent = data.value;
                }
                else if(data.type === "time"){
                    document.getElementById('resultState').style.display = 'block';
                    document.getElementById('resultText').textContent = data.value;
                }
            } catch (err) {
                console.error("Error refreshing stage:", err);
            }
        }

        async function savePlayerInfo() {
            const name = document.getElementById("playerName").value;
            const roll = document.getElementById("playerRoll").value;
            if(name && roll) {
                await fetch("/player", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, roll })
                });
                document.getElementById("savedMsg").textContent = "Info saved! Click 'Start Game' when you are ready.";
                await fetch("/set_stage/ready");
            } else {
                 document.getElementById("savedMsg").textContent = "Please enter both fields.";
            }
        }

        async function startGame() {
            await fetch("/set_stage/waiting");
        }
        
        async function getLeaderboard(){
            let r = await fetch("/leaderboard");
            let data = await r.json();
            const tableBody = document.getElementById('leaderboardTableBody');
            tableBody.innerHTML = '';
            if (data.leaderboard.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="4">No times recorded yet</td></tr>';
            } else {
                data.leaderboard.forEach((entry, i) => {
                    tableBody.innerHTML += `
                        <tr>
                            <td>#${i+1}</td>
                            <td>${parseFloat(entry[0]).toFixed(3)} ms</td>
                            <td>${entry[1]}</td>
                            <td>${entry[2]}</td>
                        </tr>`;
                });
            }
        }

        setInterval(refreshPage, 1000);
        window.onload = function() {
            refreshPage();
            getLeaderboard();
        };
    </script>
</head>
<body>
    <div class="container">
        <div id="landingState" class="landing-page">
            <div class="player-form">
                <h2>Enter Your Details</h2>
                <input type="text" id="playerName" placeholder="Enter Name">
                <input type="text" id="playerRoll" placeholder="Enter Roll Number">
                <button onclick="savePlayerInfo()">Save</button>
                <div class="msg" id="savedMsg"></div>
            </div>
        </div>

        <div id="readyPage" class="ready-page">
            <button id="startButton" class="start-button" onclick="startGame()">Start Game</button>
            <p>Press the touch sensor to begin!</p>
        </div>

        <div id="gameState" class="game-state">
            <div class='big' id="gameText"></div>
        </div>

        <div id="resultState" class="result-state">
            <div class='time' id="resultText"></div>
            <p>Returning to home screen in 4 seconds...</p>
        </div>
    </div>
    
    <div class="leaderboard">
        <h1>🏆 Fastest Reaction Leaderboard</h1>
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
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/player", methods=["POST"])
def set_player_data():
    global player_data
    data = request.json
    player_data["name"] = data.get("name", "Player")
    player_data["roll"] = data.get("roll", "N/A")
    print(f"Player data updated: {player_data}")
    return jsonify({"status": "success"})

@app.route("/set_stage/<new_stage>")
def set_stage(new_stage):
    global current_stage, ser
    current_stage["type"] = new_stage
    current_stage["value"] = None
    
    if new_stage == "waiting" and ser:
        try:
            ser.write(b'S') 
            print("Sent 'S' to Arduino to start game.")
        except serial.SerialException as e:
            print(f"Error writing to serial port: {e}")
            ser = None
    return jsonify({"status": "stage updated", "stage": new_stage})

@app.route("/leaderboard")
def get_leaderboard():
    global leaderboard
    return jsonify({"leaderboard": leaderboard})

@app.route("/stage")
def get_stage():
    global current_stage, time_shown_until
    now = time.time()
    
    if current_stage["type"] == "time" and now >= time_shown_until:
        current_stage = {"type": "landing", "value": None}
    
    return jsonify(current_stage)

def read_serial():
    global current_stage, time_shown_until, player_data, ser
    while True:
        if ser is None:
            time.sleep(2)
            try:
                ser = serial.Serial(PORT, BAUD, timeout=1)
                print(f"Successfully reconnected to serial port {PORT}.")
            except serial.SerialException as e:
                print(f"Failed to reconnect: {e}")
            continue

        if current_stage["type"] == "time":
            time.sleep(0.1)
            continue
        
        try:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            if line in ["1", "2", "3"]:
                current_stage = {"type": "countdown", "value": int(line)}
            elif line.startswith("{") and line.endswith("}"):
                data = json.loads(line)
                if "time_us" in data:
                    time_val = float(data["time_us"])
                    time_to_display = f"{time_val / 1000.0:.3f}ms"
                    
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    existing_leaderboard = []
                    try:
                        with open("leaderboard.txt", "r") as f:
                            for row in f:
                                parts = row.strip().split(",", 3)
                                if len(parts) == 4:
                                    t_val, name, roll, t_stamp = parts
                                    existing_leaderboard.append((float(t_val), name, roll, t_stamp))
                    except FileNotFoundError:
                        pass
                    
                    new_entry = (time_val, player_data["name"], player_data["roll"], timestamp)
                    existing_leaderboard.append(new_entry)
                    existing_leaderboard = sorted(existing_leaderboard, key=lambda x: x[0])
                        
                    with open("leaderboard.txt", "w") as f:
                        for t in existing_leaderboard:
                            f.write(f"{t[0]},{t[1]},{t[2]},{t[3]}\n")

                    current_stage = {"type": "time", "value": time_to_display}
                    time_shown_until = time.time() + 4

        except (ValueError, json.JSONDecodeError, serial.SerialException) as e:
            print(f"Error reading serial data: {e}")
            ser = None
            continue

if __name__ == "__main__":
    if os.path.exists("leaderboard.txt"):
        try:
            with open("leaderboard.txt", "r") as f:
                for row in f:
                    parts = row.strip().split(",", 3)
                    if len(parts) == 4:
                        leaderboard.append(tuple(parts))
        except:
            pass
    
    threading.Thread(target=read_serial, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)