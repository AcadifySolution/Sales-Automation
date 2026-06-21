#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS DASHBOARD FLASK SERVER
Local GUI backend for Sales Automation Suite.
"""

import sys
import os
import csv
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from flask import Flask, jsonify, request, render_template, send_from_directory

ROOT = Path(__file__).parent.resolve()

app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))

# Global process management
process_lock = threading.Lock()
current_process = None  # type: Optional[subprocess.Popen]
process_status = "idle"  # "idle", "running", "success", "failed"
process_action = None  # type: Optional[str]

def get_python() -> str:
    """Gets the virtual environment Python interpreter if available."""
    venv_py = ROOT / "venv" / "bin" / "python3"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable

def is_sensitive_key(key: str) -> bool:
    """Returns True if the configuration key is a sensitive credential."""
    sensitive_keys = {
        "ANTHROPIC_API_KEY",
        "HUBSPOT_ACCESS_TOKEN",
        "EMAIL_APP_PASSWORD",
        "PRODUCTHUNT_CLIENT_SECRET",
        "HUNTER_API_KEY",
        "LINKEDIN_ACCESS_TOKEN",
        "FACEBOOK_PAGE_ACCESS_TOKEN"
    }
    return key in sensitive_keys

def mask_value(key: str, val: str) -> str:
    """Masks secret values so they aren't fully exposed in the web browser."""
    if is_sensitive_key(key):
        if not val or "PLACEHOLDER" in val:
            return val
        return "********"
    return val

def read_env_file() -> Tuple[List[str], Dict[str, str]]:
    """Reads .env line by line to preserve formatting and returns values."""
    env_path = ROOT / ".env"
    lines = []
    env_dict = {}
    if not env_path.exists():
        return lines, env_dict
    
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            lines.append(line)
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                parts = stripped.split("=", 1)
                key = parts[0].strip()
                val = parts[1].strip()
                env_dict[key] = val
    return lines, env_dict

def write_env_file(new_values: Dict[str, str]) -> None:
    """Writes values back to .env while preserving comments and layout."""
    env_path = ROOT / ".env"
    lines, current_values = read_env_file()
    
    new_lines = []
    written_keys = set()
    
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            parts = stripped.split("=", 1)
            key = parts[0].strip()
            if key in new_values:
                new_val = new_values[key]
                # If submitted value is the mask, retain the actual credential
                if is_sensitive_key(key) and new_val == "********":
                    new_val = current_values.get(key, "PLACEHOLDER_DO_NOT_RUN")
                new_lines.append(f"{key}={new_val}\n")
                written_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    # Add any keys not already written
    for key, new_val in new_values.items():
        if key not in written_keys:
            if is_sensitive_key(key) and new_val == "********":
                new_val = current_values.get(key, "PLACEHOLDER_DO_NOT_RUN")
            new_lines.append(f"{key}={new_val}\n")
            
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def monitor_process(proc: subprocess.Popen, action: str):
    """Monitors the background process and sets status when done."""
    global process_status, current_process, process_action
    proc.wait()
    with process_lock:
        if current_process == proc:
            if proc.returncode == 0:
                process_status = "success"
            else:
                process_status = "failed"
            current_process = None

def run_command_in_background(args_list: List[str], action: str) -> Tuple[bool, str]:
    """Spawns an execution module in a background subprocess."""
    global current_process, process_status, process_action
    with process_lock:
        if process_status == "running" or current_process is not None:
            return False, "An execution is already in progress."
        
        log_dir = ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / "gui_run.log"
        
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"=== Starting Execution: {action} at {datetime.now().isoformat()} ===\n")
                f.write(f"Command: {' '.join(args_list)}\n\n")
        except Exception as e:
            return False, f"Failed to initialize log file: {str(e)}"
            
        try:
            log_file = open(log_path, "a", encoding="utf-8")
            
            proc = subprocess.Popen(
                args_list,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(ROOT),
                text=True
            )
            
            current_process = proc
            process_status = "running"
            process_action = action
            
            thread = threading.Thread(target=monitor_process, args=(proc, action), daemon=True)
            thread.start()
            
            return True, "Execution started."
        except Exception as e:
            process_status = "failed"
            current_process = None
            process_action = None
            return False, f"Failed to start process: {str(e)}"

# --- ROUTES ---

@app.route("/")
def home():
    """Renders the main dashboard page."""
    return render_template("index.html")

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Calculates KPI statistics from CSVs dynamically."""
    leads_path = ROOT / "data" / "leads.csv"
    calendar_path = ROOT / "data" / "content_calendar.csv"
    
    total_leads = 0
    avg_icp = 0.0
    leads_with_email = 0
    scheduled_posts = 0
    
    if leads_path.exists():
        try:
            with open(leads_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                icp_scores = []
                for row in reader:
                    total_leads += 1
                    email = row.get("Email", "").strip()
                    if email:
                        leads_with_email += 1
                    icp = row.get("ICP Score", "")
                    if icp:
                        try:
                            icp_scores.append(float(icp))
                        except ValueError:
                            pass
                if icp_scores:
                    avg_icp = round(sum(icp_scores) / len(icp_scores), 1)
        except Exception:
            pass
            
    if calendar_path.exists():
        try:
            with open(calendar_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for _ in reader:
                    scheduled_posts += 1
        except Exception:
            pass
            
    return jsonify({
        "total_leads": total_leads,
        "avg_icp": avg_icp,
        "outreach_ready": leads_with_email,
        "scheduled_posts": scheduled_posts
    })

@app.route("/api/leads", methods=["GET"])
def get_leads():
    """Returns the list of enriched leads from leads.csv."""
    leads_path = ROOT / "data" / "leads.csv"
    if not leads_path.exists():
        return jsonify([])
    
    try:
        leads = []
        with open(leads_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                leads.append(row)
        return jsonify(leads)
    except Exception as e:
        return jsonify({"error": f"Failed to read leads: {str(e)}"}), 500

@app.route("/api/calendar", methods=["GET"])
def get_calendar():
    """Returns the scheduled social posts calendar."""
    calendar_path = ROOT / "data" / "content_calendar.csv"
    if not calendar_path.exists():
        return jsonify([])
    
    try:
        calendar = []
        with open(calendar_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                calendar.append(row)
        return jsonify(calendar)
    except Exception as e:
        return jsonify({"error": f"Failed to read content calendar: {str(e)}"}), 500

@app.route("/api/config", methods=["GET"])
def get_config():
    """Returns current environment config variables masked safely."""
    try:
        _, env_dict = read_env_file()
        masked_dict = {k: mask_value(k, v) for k, v in env_dict.items()}
        return jsonify(masked_dict)
    except Exception as e:
        return jsonify({"error": f"Failed to read configuration: {str(e)}"}), 500

@app.route("/api/config", methods=["POST"])
def post_config():
    """Updates configuration settings in .env."""
    try:
        req_data = request.json
        if not req_data or not isinstance(req_data, dict):
            return jsonify({"error": "Invalid request payload"}), 400
        
        write_env_file(req_data)
        return jsonify({"status": "success", "message": "Configuration saved successfully."})
    except Exception as e:
        return jsonify({"error": f"Failed to save configuration: {str(e)}"}), 500

@app.route("/api/logs/<module>", methods=["GET"])
def get_logs(module):
    """Retrieves logs plain-text contents (last 1000 lines)."""
    module_to_file = {
        "scraper": "logs/scraper.log",
        "pipeline": "logs/pipeline.log",
        "social": "logs/social.log",
        "followup": "logs/followup.log",
        "gui": "logs/gui_run.log"
    }
    
    if module not in module_to_file:
        return jsonify({"error": "Invalid log module requested"}), 400
        
    log_path = ROOT / module_to_file[module]
    if not log_path.exists():
        return jsonify({"content": "No log records found for this module yet.\n"})
        
    try:
        # Read last 1000 lines
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            last_lines = lines[-1000:]
            return jsonify({"content": "".join(last_lines)})
    except Exception as e:
        return jsonify({"error": f"Failed to read log: {str(e)}"}), 500

@app.route("/api/run/status", methods=["GET"])
def get_run_status():
    """Returns the current process runner status."""
    global process_status, process_action
    return jsonify({
        "status": process_status,
        "action": process_action
    })

@app.route("/api/run/<action>", methods=["POST"])
def post_run(action):
    """Spawns an execution trigger in the background."""
    python_exec = get_python()
    
    # Map actions to execution commands
    action_commands = {
        "scrape": [python_exec, str(ROOT / "run.py"), "--scrape-only"],
        "pipeline": [python_exec, str(ROOT / "run.py"), "--pipeline-only"],
        "social": [python_exec, str(ROOT / "run.py"), "--social-only"],
        "followup": [python_exec, str(ROOT / "run.py"), "--followup-only"],
        "calendar": [python_exec, str(ROOT / "run.py"), "--generate"],
        "clutch": [python_exec, str(ROOT / "run.py"), "--clutch"],
        "full": [python_exec, str(ROOT / "run.py")],
        "dry_run": [python_exec, str(ROOT / "run.py"), "--dry-run"]
    }
    
    if action not in action_commands:
        return jsonify({"error": "Invalid action requested"}), 400
        
    cmd = action_commands[action]
    success, message = run_command_in_background(cmd, action)
    
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message}), 400

@app.route("/api/run/kill", methods=["POST"])
def kill_run():
    """Terminates the active background run."""
    global current_process, process_status, process_action
    with process_lock:
        if current_process is None:
            return jsonify({"status": "error", "message": "No process is currently running."}), 400
        
        try:
            current_process.terminate()
            try:
                current_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                current_process.kill()
            
            process_status = "failed"
            current_process = None
            process_action = None
            
            # Log termination to master gui run log
            log_path = ROOT / "logs" / "gui_run.log"
            if log_path.exists():
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("\n\n=== EXECUTION TERMINATED BY USER ===\n")
                    
            return jsonify({"status": "success", "message": "Process terminated successfully."})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to terminate process: {str(e)}"}), 500

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check-only":
        print("Backend server compiled and checked successfully.")
        sys.exit(0)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
