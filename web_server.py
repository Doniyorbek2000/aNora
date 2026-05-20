import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List

app = FastAPI(title="NORA Cloud Control Panel")

# In-memory queues for logs and remote commands
nora_logs = []
pending_commands = []

class LogsPayload(BaseModel):
    logs: List[str]

class CommandPayload(BaseModel):
    command: str

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    html_content = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NORA Cloud Control Dashboard</title>
    <!-- Google Fonts Outfit -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #030712;
            --panel-bg: rgba(17, 24, 39, 0.7);
            --primary: #00e5ff;
            --primary-glow: rgba(0, 229, 255, 0.4);
            --secondary: #ff4081;
            --secondary-glow: rgba(255, 64, 129, 0.4);
            --text-color: #f3f4f6;
            --text-dim: #9ca3af;
            --accent: #ffeb3b;
            --accent-glow: rgba(255, 235, 59, 0.3);
            --terminal-bg: rgba(5, 5, 10, 0.85);
            --border: rgba(255, 255, 255, 0.08);
            --border-hover: rgba(0, 229, 255, 0.3);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            overflow-x: hidden;
            background-image: 
                radial-gradient(at 10% 20%, rgba(0, 229, 255, 0.08) 0px, transparent 50%),
                radial-gradient(at 90% 80%, rgba(255, 64, 129, 0.08) 0px, transparent 50%);
            background-attachment: fixed;
            min-height: 100vh;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
        }

        .logo-section {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .nora-orb {
            width: 45px;
            height: 45px;
            background: radial-gradient(circle, var(--primary) 0%, #0088aa 100%);
            border-radius: 50%;
            box-shadow: 0 0 20px var(--primary-glow);
            animation: pulse 3s infinite alternate;
        }

        @keyframes pulse {
            0% { transform: scale(1); box-shadow: 0 0 15px var(--primary-glow); }
            100% { transform: scale(1.1); box-shadow: 0 0 30px rgba(0, 229, 255, 0.8); }
        }

        h1 {
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #fff 30%, var(--primary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .status-badge {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid #10b981;
            color: #34d399;
            padding: 6px 16px;
            border-radius: 30px;
            font-size: 0.9rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: #34d399;
            border-radius: 50%;
            animation: blink 1.5s infinite;
        }

        @keyframes blink {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 1; }
        }

        .grid-layout {
            display: grid;
            grid-template-columns: 1fr 1.2fr;
            gap: 30px;
        }

        @media (max-width: 900px) {
            .grid-layout {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--panel-bg);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(12px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .card:hover {
            border-color: var(--border-hover);
            box-shadow: 0 10px 40px rgba(0, 229, 255, 0.1);
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--primary), transparent);
            opacity: 0.5;
        }

        h2 {
            font-size: 1.4rem;
            font-weight: 600;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            gap: 10px;
            color: #fff;
        }

        .form-group {
            margin-bottom: 20px;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-size: 0.9rem;
            color: var(--text-dim);
        }

        .input-wrapper {
            position: relative;
        }

        input[type="text"] {
            width: 100%;
            padding: 14px 20px;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border);
            border-radius: 12px;
            color: #fff;
            font-family: inherit;
            font-size: 1rem;
            transition: all 0.3s ease;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.2);
        }

        .btn {
            width: 100%;
            padding: 14px 20px;
            background: linear-gradient(135deg, var(--primary) 0%, #0088aa 100%);
            border: none;
            border-radius: 12px;
            color: #030712;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0, 229, 255, 0.3);
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 229, 255, 0.5);
            filter: brightness(1.1);
        }

        .btn:active {
            transform: translateY(0);
        }

        .preset-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-top: 20px;
        }

        .preset-btn {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            color: var(--text-color);
            padding: 12px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.85rem;
            font-weight: 500;
            text-align: left;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .preset-btn:hover {
            background: rgba(0, 229, 255, 0.08);
            border-color: var(--primary);
            color: #fff;
            transform: scale(1.02);
        }

        .terminal {
            background: var(--terminal-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            height: 480px;
            font-family: 'JetBrains Mono', monospace;
            padding: 20px;
            overflow-y: auto;
            font-size: 0.9rem;
            line-height: 1.6;
            display: flex;
            flex-direction: column;
            gap: 8px;
            box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.8);
        }

        /* Scrollbar styling */
        .terminal::-webkit-scrollbar, ::-webkit-scrollbar {
            width: 8px;
        }
        .terminal::-webkit-scrollbar-track, ::-webkit-scrollbar-track {
            background: rgba(0,0,0,0.1);
        }
        .terminal::-webkit-scrollbar-thumb, ::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
        }
        .terminal::-webkit-scrollbar-thumb:hover, ::-webkit-scrollbar-thumb:hover {
            background: var(--primary);
        }

        .log-entry {
            border-left: 2px solid var(--primary);
            padding-left: 10px;
            animation: fadeIn 0.3s ease forwards;
        }

        .log-entry.you {
            border-color: var(--text-color);
            color: #e8e8e8;
        }

        .log-entry.nora {
            border-color: var(--primary);
            color: var(--primary);
        }

        .log-entry.sys {
            border-color: var(--accent);
            color: var(--accent);
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .badge-mini {
            font-size: 0.7rem;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
            font-weight: 700;
            margin-right: 6px;
            background: rgba(0, 229, 255, 0.1);
            border: 1px solid var(--primary);
        }

        .log-entry.you .badge-mini {
            background: rgba(255, 255, 255, 0.1);
            border-color: #fff;
        }

        .log-entry.sys .badge-mini {
            background: rgba(255, 235, 59, 0.1);
            border-color: var(--accent);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-section">
                <div class="nora-orb"></div>
                <div>
                    <h1>NORA</h1>
                    <p style="color: var(--text-dim); font-size: 0.85rem; font-weight: 400; letter-spacing: 1px;">CLOUD GATEWAY</p>
                </div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>NORA ONLINE</span>
            </div>
        </header>

        <div class="grid-layout">
            <!-- Left Side: Control panel -->
            <div style="display: flex; flex-direction: column; gap: 30px;">
                <div class="card">
                    <h2>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        Remotely Control NORA
                    </h2>
                    <form id="cmdForm" onsubmit="sendCommand(event)">
                        <div class="form-group">
                            <label for="cmdInput">Matnli Buyruq (yoki Ovozli xabar matni)</label>
                            <input type="text" id="cmdInput" placeholder="Masalan: Ob-havo qanday?, Musiqani yoq, etc." required>
                        </div>
                        <button type="submit" class="btn">Buyruqni Yuborish</button>
                    </form>

                    <div style="margin-top: 30px; border-top: 1px solid var(--border); padding-top: 20px;">
                        <label>Tezkor Tizim Buyruqlari</label>
                        <div class="preset-grid">
                            <button class="preset-btn" onclick="sendPreset('Musiqani to\'xtat')">🔊 Musiqani To'xtat</button>
                            <button class="preset-btn" onclick="sendPreset('Musiqani qo\'y')">🎶 Keyingi Musiqa</button>
                            <button class="preset-btn" onclick="sendPreset('Ovozli yozishni boshla')">🎙️ Dictation ON</button>
                            <button class="preset-btn" onclick="sendPreset('Ovozli yozishni to\'xtat')">🤫 Dictation OFF</button>
                            <button class="preset-btn" onclick="sendPreset('Toshkentdagi ob-havo')">🌦️ Toshkent Ob-havo</button>
                            <button class="preset-btn" onclick="sendPreset('Google Chrome-ni och')">🌐 Chrome Ochish</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Side: Terminal console -->
            <div class="card">
                <h2>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17l6-6-6-6M12 19h8"></path></svg>
                    NORA Live Console Logs
                </h2>
                <div class="terminal" id="terminal">
                    <div class="log-entry sys"><span class="badge-mini">sys</span>Veb boshqaruv paneli ishga tushdi. Aloqa kutilmoqda...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function sendCommand(event) {
            if(event) event.preventDefault();
            const input = document.getElementById('cmdInput');
            const cmd = input.value.strip ? input.value.strip() : input.value;
            if(!cmd) return;
            
            try {
                const response = await fetch('/api/send_command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                if(response.ok) {
                    input.value = '';
                    appendSystemLog(`Muvaffaqiyatli yuborildi: "${cmd}"`);
                }
            } catch(e) {
                console.error(e);
            }
        }

        async function sendPreset(cmd) {
            try {
                const response = await fetch('/api/send_command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                if(response.ok) {
                    appendSystemLog(`Muvaffaqiyatli yuborildi: "${cmd}"`);
                }
            } catch(e) {
                console.error(e);
            }
        }

        function appendSystemLog(msg) {
            const terminal = document.getElementById('terminal');
            const div = document.createElement('div');
            div.className = 'log-entry sys';
            div.innerHTML = `<span class="badge-mini">sys</span>${msg}`;
            terminal.appendChild(div);
            terminal.scrollTop = terminal.scrollHeight;
        }

        // Poll logs every 1.5 seconds
        async function pollLogs() {
            try {
                const response = await fetch('/api/get_logs');
                if(response.ok) {
                    const data = await response.json();
                    const terminal = document.getElementById('terminal');
                    if(data.logs && data.logs.length > 0) {
                        data.logs.forEach(log => {
                            const div = document.createElement('div');
                            const lowerLog = log.toLowerCase();
                            
                            if (lowerLog.startsWith('you:')) {
                                div.className = 'log-entry you';
                                div.innerHTML = `<span class="badge-mini">you</span>${escapeHtml(log.substring(4).trim())}`;
                            } else if (lowerLog.startsWith('nora:')) {
                                div.className = 'log-entry nora';
                                div.innerHTML = `<span class="badge-mini">nora</span>${escapeHtml(log.substring(5).trim())}`;
                            } else {
                                div.className = 'log-entry sys';
                                div.innerHTML = `<span class="badge-mini">sys</span>${escapeHtml(log)}`;
                            }
                            
                            terminal.appendChild(div);
                        });
                        terminal.scrollTop = terminal.scrollHeight;
                    }
                }
            } catch(e) {
                console.error("Polling logs failed", e);
            }
            setTimeout(pollLogs, 1500);
        }

        function escapeHtml(text) {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return text.replace(/[&<>"']/g, function(m) { return map[m]; });
        }

        // Start polling logs immediately
        pollLogs();
    </script>
</body>
</html>"""
    return html_content

@app.get("/api/get_commands")
async def get_commands():
    global pending_commands
    cmds = list(pending_commands)
    pending_commands.clear()
    return {"commands": cmds}

@app.post("/api/send_command")
async def send_command(payload: CommandPayload):
    global pending_commands
    pending_commands.append(payload.command)
    return {"status": "success"}

@app.post("/api/post_logs")
async def post_logs(payload: LogsPayload):
    global nora_logs
    nora_logs.extend(payload.logs)
    # keep last 200 logs
    if len(nora_logs) > 200:
        nora_logs = nora_logs[-200:]
    return {"status": "success"}

@app.get("/api/get_logs")
async def get_logs():
    global nora_logs
    logs = list(nora_logs)
    nora_logs.clear()
    return {"logs": logs}
