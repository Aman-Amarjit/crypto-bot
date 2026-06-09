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

# Global state to track the comment reply process
replies_process = None
replies_thread = None
replies_lock = threading.Lock()

# Global state to track the daily thought process
thought_process = None
thought_thread = None
thought_lock = threading.Lock()

def load_env_vars():
    env_file = ".env"
    vars_list = [
        "THREADS_USER_ID", "THREADS_ACCESS_TOKEN", "GH_PAT",
        "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
        "GROQ_API_KEY", "POST_TOPIC", "POLLINATIONS_API_KEY",
        "GEMINI_API_KEY", "AUTOMATION_PAUSED", "HF_API_TOKEN",
        "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"
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
    cmd = ["venv/bin/python", "main.py", "--force"]
    if topic:
        cmd.insert(2, topic)  # insert before --force so argparse sees: main.py TOPIC --force
        
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

def run_replies_subprocess():
    global replies_process
    cmd = ["venv/bin/python", "reply.py"]
        
    try:
        log_file = "data/bot.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"\n=== Comment Check Triggered Manually at {time_str()} ===\n")
            
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        with replies_lock:
            replies_process = proc
            
        with open(log_file, "a") as f:
            for line in proc.stdout:
                f.write(line)
                f.flush()
                
        proc.wait()
    except Exception as e:
        with open("data/bot.log", "a") as f:
            f.write(f"\n[Dashboard Error] Replies execution failed: {e}\n")
    finally:
        with replies_lock:
            replies_process = None

def run_thought_subprocess():
    global thought_process
    cmd = ["venv/bin/python", "thought.py", "--force"]
        
    try:
        log_file = "data/thought_bot.log"
        # We also write summary logs to data/bot.log so it shows on the main dashboard logs
        main_log_file = "data/bot.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        start_msg = f"\n=== Daily Thought Run Triggered Manually at {time_str()} ===\n"
        with open(log_file, "w") as f:
            f.write(start_msg)
        with open(main_log_file, "a") as f:
            f.write(start_msg)
            
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        with thought_lock:
            thought_process = proc
            
        # Write output to both logs
        for line in proc.stdout:
            with open(log_file, "a") as f:
                f.write(line)
                f.flush()
            with open(main_log_file, "a") as f:
                f.write(line)
                f.flush()
                
        proc.wait()
    except Exception as e:
        err_msg = f"\n[Dashboard Error] Daily thought execution failed: {e}\n"
        with open("data/bot.log", "a") as f:
            f.write(err_msg)
    finally:
        with thought_lock:
            thought_process = None

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
        # Return last 250 lines of logs
        return jsonify({"logs": "".join(lines[-250:])})
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

# --- Comment Reply API Endpoints ---

@app.route('/api/replies/status', methods=['GET'])
def get_replies_status():
    with replies_lock:
        is_running = replies_process is not None
        pid = replies_process.pid if is_running else None
    return jsonify({
        "running": is_running,
        "pid": pid
    })

@app.route('/api/replies/run', methods=['POST'])
def run_replies():
    global replies_thread
    with replies_lock:
        if replies_process is not None:
            return jsonify({"error": "A comment-reply execution is already in progress"}), 409

    replies_thread = threading.Thread(target=run_replies_subprocess)
    replies_thread.daemon = True
    replies_thread.start()
    
    return jsonify({"message": "Comment replies check started"})

@app.route('/api/replies/history', methods=['GET'])
def get_replies_history():
    db_path = "data/bot.db"
    if not os.path.exists(db_path):
        return jsonify([])
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT comment_id, post_id, commenter_username, comment_text, reply_text, timestamp, status
            FROM replied_comments
            ORDER BY timestamp DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for r in rows:
            history.append({
                "comment_id": r[0],
                "post_id": r[1],
                "commenter_username": r[2],
                "comment_text": r[3],
                "reply_text": r[4],
                "timestamp": r[5],
                "status": r[6]
            })
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Daily Thoughts API Endpoints ---

@app.route('/api/thoughts/status', methods=['GET'])
def get_thoughts_status():
    with thought_lock:
        is_running = thought_process is not None
        pid = thought_process.pid if is_running else None
    return jsonify({
        "running": is_running,
        "pid": pid
    })

@app.route('/api/thoughts/run', methods=['POST'])
def run_thought():
    global thought_thread
    with thought_lock:
        if thought_process is not None:
            return jsonify({"error": "A daily thought execution is already in progress"}), 409

    thought_thread = threading.Thread(target=run_thought_subprocess)
    thought_thread.daemon = True
    thought_thread.start()
    
    return jsonify({"message": "Daily thought execution started"})

@app.route('/api/thoughts/history', methods=['GET'])
def get_thoughts_history():
    history_file = "data/thought_history.json"
    if not os.path.exists(history_file):
        return jsonify([])
    try:
        with open(history_file, 'r') as f:
            history = json.load(f)
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync', methods=['POST'])
def sync_data():
    try:
        import subprocess
        # Discard local changes in data files to prevent merge conflicts
        subprocess.run(["git", "checkout", "--", "data/history.json", "data/thought_history.json", "data/bot.db", "data/bot.log"], capture_output=True)
        
        # Configure local git user if not configured
        subprocess.run(["git", "config", "user.name", "Local Bot Dashboard"], capture_output=True)
        subprocess.run(["git", "config", "user.email", "local@bot.dashboard"], capture_output=True)
        
        # Fetch the remote changes
        fetch_res = subprocess.run(["git", "fetch", "origin", "main"], capture_output=True, text=True)
        if fetch_res.returncode != 0:
            return jsonify({"error": f"Git fetch failed: {fetch_res.stderr}"}), 500
            
        # Merge preferring remote changes for data files (this automatically handles conflicts)
        merge_res = subprocess.run(["git", "merge", "-X", "theirs", "origin/main", "-m", "chore: sync remote data"], capture_output=True, text=True)
        if merge_res.returncode != 0:
            return jsonify({"error": f"Git merge failed: {merge_res.stderr}"}), 500
            
        return jsonify({"message": "Dashboard data successfully synchronized with GitHub!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ensure static directory exists
    os.makedirs(app.static_folder, exist_ok=True)
    
    # Run server locally on 0.0.0.0:5000
    app.run(host='0.0.0.0', port=5000, debug=True)
