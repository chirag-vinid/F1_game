import serial
import json
from flask import Flask, render_template_string, jsonify, request
import threading
import time
import datetime
import os
import cv2

PORT = "COM7"
BAUD = 9600
ser = None
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
except serial.SerialException as e:
    print(f"Error: Could not open serial port {PORT}. Please check the connection and port number.")
    print(e)

app = Flask(__name__)

# Ensure images folder exists
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

leaderboard = []
current_stage = {"type": "landing", "value": None}
time_shown_until = 0
last_top_10_rank = None
temp_new_entry = None
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
        .photo-button { padding: 10px 20px; font-size: 18px; background: #007bff; color: #fff; border: none; border-radius: 5px; cursor: pointer; margin-top: 10px; }
        .msg { font-size: 24px; color: #fff; margin-top: 20px; }
    </style>
    <script>
        async function refreshPage(){
            try {
                let r = await fetch("/stage");
                if (!r.ok) return;
                let data = await r.json();

                // Hide all states
                document.getElementById('landingState').style.display = 'none';
                document.getElementById('readyPage').style.display = 'none';
                document.getElementById('gameState').style.display = 'none';
                document.getElementById('resultState').style.display = 'none';

                // Show the correct state based on current_stage
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
                else if(data.type === "time" || data.type === "new_record"){
                    document.getElementById('resultState').style.display = 'block';
                    document.getElementById('resultText').textContent = data.value;
                    if(data.type === "new_record"){
                        document.getElementById('photoButton').style.display = 'block';
                    } else {
                        document.getElementById('photoButton').style.display = 'none';
                    }
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

        async function takePicture() {
            const res = await fetch("/take_picture");
            const data = await res.json();
            if (data.status === "success") {
                alert("Picture saved for your new rank!");
                window.location.reload(); 
            } else {
                alert("Failed to take picture. " + data.message);
            }
        }

        setInterval(refreshPage, 1000);
        window.onload = refreshPage;
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
            <p>Returning to home screen in 10 seconds...</p>
            <button id="photoButton" class="photo-button" onclick="takePicture()">Click Picture</button>
        </div>
    </div>
</body>
</html>
"""

def capture_webcam_image(filename):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam!")
        return False
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(os.path.join(IMAGES_DIR, filename), frame)
        print(f"Webcam image saved to {filename}")
        return True
    else:
        print("Failed to capture webcam image.")
        return False
    cap.release()

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

@app.route("/take_picture")
def take_picture_route():
    global temp_new_entry, leaderboard
    if temp_new_entry:
        name = temp_new_entry[1].replace(" ", "_")
        roll = temp_new_entry[2].replace("/", "_")
        time_us = temp_new_entry[0]
        filename = f"{name}_{time_us:.0f}.jpg"
        
        if capture_webcam_image(filename):
            new_entry_with_photo = (temp_new_entry[0], temp_new_entry[1], temp_new_entry[2], temp_new_entry[3], filename)
            
            existing_leaderboard = []
            try:
                with open("leaderboard.txt", "r") as f:
                    for row in f:
                        parts = row.strip().split(",", 4)
                        if len(parts) == 5:
                            t_us, name, roll, t_stamp, fname = parts
                            existing_leaderboard.append((float(t_us), name, roll, t_stamp, fname))
            except FileNotFoundError:
                pass
            
            existing_leaderboard.append(new_entry_with_photo)
            existing_leaderboard = sorted(existing_leaderboard, key=lambda x: x[0])
            leaderboard[:] = existing_leaderboard
            
            with open("leaderboard.txt", "w") as f:
                for t in existing_leaderboard:
                    f.write(f"{t[0]},{t[1]},{t[2]},{t[3]},{t[4]}\n")

            temp_new_entry = None
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "Webcam not available."}), 500
    
    return jsonify({"status": "error", "message": "No new record to photograph."}), 400

@app.route("/stage")
def get_stage():
    global current_stage, time_shown_until, temp_new_entry
    now = time.time()

    # This is the corrected logic. It will now automatically save the entry
    # and reset the page after 10 seconds if no picture is taken.
    if current_stage["type"] in ["time", "new_record"] and now >= time_shown_until:
        if temp_new_entry is not None:
            # New entry exists but no photo was taken. Save with a placeholder.
            existing_leaderboard = []
            try:
                with open("leaderboard.txt", "r") as f:
                    for row in f:
                        parts = row.strip().split(",", 4)
                        if len(parts) == 5:
                            t_us, name, roll, t_stamp, fname = parts
                            existing_leaderboard.append((float(t_us), name, roll, t_stamp, fname))
            except FileNotFoundError:
                pass
            
            new_entry_with_placeholder = (temp_new_entry[0], temp_new_entry[1], temp_new_entry[2], temp_new_entry[3], "no_photo.png")
            existing_leaderboard.append(new_entry_with_placeholder)
            existing_leaderboard = sorted(existing_leaderboard, key=lambda x: x[0])
            leaderboard[:] = existing_leaderboard

            with open("leaderboard.txt", "w") as f:
                for t in existing_leaderboard:
                    f.write(f"{t[0]},{t[1]},{t[2]},{t[3]},{t[4]}\n")

            temp_new_entry = None
        
        current_stage = {"type": "landing", "value": None}
    
    return jsonify(current_stage)

def read_serial():
    global current_stage, time_shown_until, player_data, ser, temp_new_entry
    while True:
        if ser is None:
            time.sleep(2)
            try:
                ser = serial.Serial(PORT, BAUD, timeout=1)
                print(f"Successfully reconnected to serial port {PORT}.")
            except serial.SerialException as e:
                print(f"Failed to reconnect: {e}")
            continue

        if current_stage["type"] in ["time", "new_record"]:
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
                                parts = row.strip().split(",", 4)
                                if len(parts) == 5:
                                    t_us, name, roll, t_stamp, fname = parts
                                    existing_leaderboard.append((float(t_us), name, roll, t_stamp, fname))
                    except FileNotFoundError:
                        pass
                    
                    new_entry = (time_val, player_data["name"], player_data["roll"], timestamp, "N/A")
                    
                    if len(existing_leaderboard) < 10 or time_val < max(t[0] for t in existing_leaderboard):
                        temp_new_entry = new_entry
                        current_stage = {"type": "new_record", "value": time_to_display}
                    else:
                        current_stage = {"type": "time", "value": time_to_display}

                    time_shown_until = time.time() + 10

        except (ValueError, json.JSONDecodeError, serial.SerialException) as e:
            print(f"Error reading serial data: {e}")
            ser = None
            continue

if __name__ == "__main__":
    if os.path.exists("leaderboard.txt"):
        try:
            with open("leaderboard.txt", "r") as f:
                for row in f:
                    parts = row.strip().split(",", 4)
                    if len(parts) == 5:
                        leaderboard.append(tuple(parts))
        except:
            pass
    
    threading.Thread(target=read_serial, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)