import os
import sys
import json
import subprocess
import threading
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder='static')

# Global state to track the bot execution process
running_process = None
running_thread = None
process_lock = threading.Lock()

def load_env_vars():
    env_file = ".env"
    vars_list = [
        "THREADS_USER_ID", "THREADS_ACCESS_TOKEN", "GH_PAT",
        "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
        "GROQ_API_KEY", "POST_TOPIC", "POLLINATIONS_API_KEY"
    ]
    env_vars = {v: "" for v in vars_list}
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    if key in env_vars:
                        env_vars[key] = val.strip()
    return env_vars

def write_env_vars(new_vars):
    env_file = ".env"
    lines = []
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            lines = f.readlines()

    keys_written = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key, _ = stripped.split('=', 1)
            key = key.strip()
            if key in new_vars:
                new_lines.append(f"{key}={new_vars[key]}\n")
                keys_written.add(key)
                continue
        new_lines.append(line)

    for key, val in new_vars.items():
        if key not in keys_written:
            new_lines.append(f"{key}={val}\n")

    with open(env_file, 'w') as f:
        f.writelines(new_lines)

def run_bot_subprocess(topic=None):
    global running_process
    cmd = ["venv/bin/python", "main.py"]
    if topic:
        cmd.append(topic)
        
    try:
        # Clear log file before start so it starts fresh
        log_file = "data/bot.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "w") as f:
            f.write(f"=== Bot Run Triggered Manually at {time_str()} ===\n")
            
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        with process_lock:
            running_process = proc
            
        # Write live output to bot.log
        with open(log_file, "a") as f:
            for line in proc.stdout:
                f.write(line)
                f.flush()
                
        proc.wait()
    except Exception as e:
        with open("data/bot.log", "a") as f:
            f.write(f"\n[Dashboard Error] Subprocess execution failed: {e}\n")
    finally:
        with process_lock:
            running_process = None

def time_str():
    from datetime import datetime
    return datetime.now().isoformat()

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

@app.route('/api/history', methods=['GET'])
def get_history():
    history_file = "data/history.json"
    if not os.path.exists(history_file):
        return jsonify([])
    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    log_file = "data/bot.log"
    if not os.path.exists(log_file):
        return jsonify({"logs": "No logs available yet."})
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        # Return last 150 lines of logs
        return jsonify({"logs": "".join(lines[-150:])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    if request.method == 'GET':
        return jsonify(load_env_vars())
    else:
        new_config = request.json
        if not new_config or not isinstance(new_config, dict):
            return jsonify({"error": "Invalid request body"}), 400
        try:
            write_env_vars(new_config)
            return jsonify({"message": "Configuration updated successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    with process_lock:
        is_running = running_process is not None
        pid = running_process.pid if is_running else None
    return jsonify({
        "running": is_running,
        "pid": pid
    })

@app.route('/api/run', methods=['POST'])
def run_bot():
    global running_thread
    with process_lock:
        if running_process is not None:
            return jsonify({"error": "A bot execution is already in progress"}), 409

    data = request.json or {}
    topic = data.get("topic")
    
    running_thread = threading.Thread(target=run_bot_subprocess, args=(topic,))
    running_thread.daemon = True
    running_thread.start()
    
    return jsonify({"message": "Bot execution started"})

if __name__ == '__main__':
    # Ensure static directory exists
    os.makedirs(app.static_folder, exist_ok=True)
    
    # Run server locally on 0.0.0.0:5000
    app.run(host='0.0.0.0', port=5000, debug=True)
