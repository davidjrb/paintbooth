from flask import Flask, Response, jsonify, render_template_string, request
from pylogix import PLC
import json, time

# ---- CONFIG ----
PLC_IP = "192.168.1.1"  # CompactLogix PLC IP for Booth 1
# Define the PLC tags to read for Booth 1 status
TAGS = [
    "M[0].0",       # System ON (Booth 1 System Control Enabled)
    "M[40].0",      # Heat ENABLED (Booth 1 Heat Control Enabled)
    "M[0].11",      # Bake Mode ACTIVE (Booth 1 Bake Cycle Active)
    "B1_Bake_Time_ACC",  # Bake Timer Accumulator (REAL, minutes)
    "W16[2]",       # Current Temperature (Booth 1, INT scaled x100)
    "W16[1]",       # Temperature Setpoint (Booth 1 PID, INT scaled x100)
    "M[1].4",       # Mode: Restart Bake Cycle (AUTO)
    "M[1].5",       # Mode: End Bake Cycle (MANUAL)
    "M[40].4",      # Cooldown Active Status
    "TMR[6].ACC",   # Cooldown Timer Accumulator (ms)
    "B1_Bake_Time", # Bake Timer Preset (REAL, minutes)
    "M[3].0",       # Lights Status
    "M[1].0",       # Lights ON Command
    "M[0].15",      # Lights OFF Command
    "TMR[6].PRE",   # Cooldown Timer Preset (DINT, ms)
    "W00[15]",      # Spray Temperature Setpoint (INT, scaled x100)
]
POLL_SEC = 1.0  # polling interval in seconds

app = Flask(__name__)

# HTML template for the dashboard page
PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Paint Booth 1 Live Status</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root { color-scheme: dark; }
    html, body { height: 100%; overflow: hidden; }
    body {
      background: #0b0e13;
      color: #e6e6e6;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      font-size: 4vh; /* Increased from 2vh */
      display: flex;
      flex-direction: column;
    }
    header { 
      padding: 1vh 2vw; 
      border-bottom: 1px solid #1f2430; 
      display: flex; 
      align-items: center; 
      gap: 12px; 
      flex-shrink: 0;
      height: 10vh; /* Increased from 8vh */
    }
    .dot { width: 2vh; height: 2vh; border-radius: 50%; background: #3fdc5a; box-shadow: 0 0 8px #3fdc5a; }
    h1 { font-size: 5vh; margin: 0; letter-spacing: 0.3px; } /* Increased from 2.5vh */
    main { 
      flex-grow: 1; 
      padding: 1vh 2vw; 
      display: flex; 
      flex-direction: column; 
      justify-content: center; 
      overflow: hidden; 
    }
    table { 
      width: 100%; 
      height: 100%; 
      border-collapse: separate; 
      border-spacing: 0; 
      overflow: hidden; 
      border-radius: 14px; 
      box-shadow: 0 6px 24px rgba(0,0,0,.35); 
    }
    th, td { 
      text-align: left; 
      padding: 0 2vw; 
      border-bottom: 1px solid #222735; 
      height: 10%; /* Distribute rows evenly */
    }
    th { background: #131826; font-weight: 600; color: #9fb0ff; border-bottom-color: #20263a; }
    tr:last-child td { border-bottom: none; }
    .tag { color: #b7c3ff; font-size: 1.5em; } /* Increased to match val */
    .val { color: #ffd28a; font-weight: bold; font-size: 1.5em; } /* Increased from 1.1em */
    .small { color: #7b8aa8; font-size: 2vh; } /* Increased from 1.5vh */

    .status-cell { width: 8vw; text-align: center; padding: 0; }
    .status-indicator {
      width: 4vh;
      height: 4vh;
      background: #333;
      margin: 0 auto;
      border-radius: 4px;
      transition: background 0.3s;
    }
    .status-on { background: #3fdc5a; box-shadow: 0 0 10px #3fdc5a; }
    .status-off { background: #ff4444; box-shadow: 0 0 10px #ff4444; }
    .controls-btn {
      background: #2196F3;
      color: white;
      text-decoration: none;
      padding: 3vh 3vw; /* Increased vertical padding to double height */
      border-radius: 8px;
      font-size: 1.2em; /* Large and readable */
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 2px;
      box-shadow: 0 4px 10px rgba(0,0,0,0.4);
      transition: background 0.2s, transform 0.1s;
      display: inline-block;
      line-height: 1;
    }
    .controls-btn:hover { background: #1976D2; }
    .controls-btn:active { transform: translateY(2px); }
  </style>
</head>
<body>
  <header>
    <div class="dot"></div>
    <h1>Paint Booth 1 Dashboard</h1>
    <div class="small" style="margin-left:auto;">PLC: {{ plc_ip }}</div>
  </header>
  <main>
    <table>
      <thead>
        <tr>
          <th class="status-cell">Status</th>
          <th>Tag</th>
          <th><a href="/controls" class="controls-btn">CONTROLS</a></th>
        </tr>
      </thead>
      <tbody id="rows">
        <tr><td class="status-cell"><div id="s_M_0_0" class="status-indicator"></div></td><td class="tag">System ON</td>           <td class="val" id="M_0_0">—</td></tr>
        <tr><td class="status-cell"><div id="s_M_40_0" class="status-indicator"></div></td><td class="tag">Heat ENABLED</td>        <td class="val" id="M_40_0">—</td></tr>
        <tr><td class="status-cell"><div id="s_M_0_11" class="status-indicator"></div></td><td class="tag">Bake mode ACTIVE</td>    <td class="val" id="M_0_11">—</td></tr>
        <tr><td class="status-cell"><div id="s_B1_Bake_Time_ACC" class="status-indicator"></div></td><td class="tag">Bake Timer</td>          <td class="val" id="B1_Bake_Time_ACC">—</td></tr>
        <tr><td class="status-cell"><div id="s_W16_2" class="status-indicator"></div></td><td class="tag">Current Temperature</td> <td class="val" id="W16_2">—</td></tr>
        <tr><td class="status-cell"><div id="s_W16_1" class="status-indicator"></div></td><td class="tag">Temperature Setpoint</td><td class="val" id="W16_1">—</td></tr>
        <tr><td class="status-cell"><div id="s_mode" class="status-indicator"></div></td><td class="tag">Mode (Auto/Manual)</td>  <td class="val" id="mode">—</td></tr>
        <tr><td class="status-cell"><div id="s_M_40_4" class="status-indicator"></div></td><td class="tag">Cooldown ACTIVE</td>     <td class="val" id="M_40_4">—</td></tr>
        <tr><td class="status-cell"><div id="s_TMR_6_ACC" class="status-indicator"></div></td><td class="tag">Cooldown Timer</td>      <td class="val" id="TMR_6_ACC">—</td></tr>
      </tbody>
    </table>
    <div class="small" style="margin-top:10px" id="status">connecting…</div>
  </main>
  <script>
    const statusEl = document.getElementById('status');
    
    function updateStatusIndicator(id, isGreen) {
      const el = document.getElementById(id);
      if (el) {
        el.className = 'status-indicator ' + (isGreen ? 'status-on' : 'status-off');
      }
    }

    function applyUpdate(data) {
      const vals = data.values || {};

      // Update values for each tag in the payload
      for (const [tag, val] of Object.entries(vals)) {
        // Skip mode bits here; handle mode display after loop
        if (tag === "M[1].4" || tag === "M[1].5") continue;
        // Determine the element ID corresponding to the tag
        // Convert brackets/dots to underscores to match HTML IDs (e.g. M[0].0 -> M_0_0)
        let elementId = tag.replace(/\[|\]|\./g, '_').replace('__', '_').replace(/_$/, '');
        const el = document.getElementById(elementId);
        if (!el) continue;

        if (tag === "B1_Bake_Time_ACC") {
          // Display bake timer in MM:SS min
          let totalMin = parseFloat(val);
          let m = Math.floor(totalMin);
          let s = Math.round((totalMin - m) * 60);
          if (s === 60) { m++; s = 0; }
          el.textContent = m + ":" + s.toString().padStart(2, '0') + " min";
        } else if (tag === "TMR[6].ACC") {
          // Cooldown timer ACC (ms) → MM:SS min
          let totalSec = parseInt(val, 10) / 1000;
          let m = Math.floor(totalSec / 60);
          let s = Math.floor(totalSec % 60);
          el.textContent = m + ":" + s.toString().padStart(2, '0') + " min";
          continue;
        } else if (tag === "W16[1]" || tag === "W16[2]") {
          // Temperature setpoint/current: divide by 100 to get one decimal + °F
          el.textContent = (parseInt(val) / 100.0).toFixed(1) + " °F";
        } else {
          // Booleans or other values: show as ON/OFF if boolean, or numeric directly
          if (val === 1) {
            el.textContent = "ON";
          } else if (val === 0) {
            el.textContent = "OFF";
          } else {
            el.textContent = val;
          }
        }
      }

      // Determine and display mode (Auto/Manual) based on mode bits
      let isAuto = false;
      if (vals.hasOwnProperty("M[1].4") && vals.hasOwnProperty("M[1].5")) {
        const modeEl = document.getElementById('mode');
        if (modeEl) {
          const autoMode = vals["M[1].4"];
          const manualMode = vals["M[1].5"];
          if (autoMode === 1) {
            modeEl.textContent = "AUTO";
            isAuto = true;
          } else if (manualMode === 1) {
            modeEl.textContent = "MANUAL";
            isAuto = false;
          } else {
            modeEl.textContent = "—";
            isAuto = false;
          }
        }
      }
      
      // Update Status Indicators
      // System ON: Green if ON (1)
      updateStatusIndicator('s_M_0_0', vals['M[0].0'] === 1);
      
      // Heat ENABLED: Green if ON (1)
      updateStatusIndicator('s_M_40_0', vals['M[40].0'] === 1);
      
      // Bake mode ACTIVE: Green if ON (1)
      updateStatusIndicator('s_M_0_11', vals['M[0].11'] === 1);
      
      // Bake Timer: Green if > 0
      updateStatusIndicator('s_B1_Bake_Time_ACC', parseFloat(vals['B1_Bake_Time_ACC']) > 0);
      
      // Current Temperature: Green if >= Setpoint
      // Note: Values are scaled integers (e.g. 12000 = 120.00). Comparison works directly.
      let curTemp = parseInt(vals['W16[2]'] || 0);
      let spTemp = parseInt(vals['W16[1]'] || 0);
      updateStatusIndicator('s_W16_2', curTemp >= spTemp);
      
      // Temperature Setpoint: Green when Bake mode ACTIVE ON
      updateStatusIndicator('s_W16_1', vals['M[0].11'] === 1);
      
      // Mode: Green when AUTO
      updateStatusIndicator('s_mode', isAuto);
      
      // Cooldown ACTIVE: Green when ON (1)
      updateStatusIndicator('s_M_40_4', vals['M[40].4'] === 1);
      
      // Cooldown Timer: Green when > 0
      updateStatusIndicator('s_TMR_6_ACC', parseInt(vals['TMR[6].ACC'] || 0) > 0);

      // Update status text (timestamp or error)
      if (data.error) {
        statusEl.textContent = "error: " + data.error;
      } else {
        statusEl.textContent = "last update: " + new Date().toLocaleTimeString();
      }
    }

    function connect() {
      const ev = new EventSource("/stream");
      ev.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          applyUpdate(payload);
        } catch (err) {
          console.error("Failed to parse update", err);
        }
      };
      ev.onerror = () => {
        statusEl.textContent = "disconnected, retrying…";
        // Attempt reconnect after a delay
        setTimeout(connect, 3000);
      };
    }
    connect();
  </script>
</body>
</html>
"""

CONTROLS_PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Controls - Paint Booth 1</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root { color-scheme: dark; }
    html, body { height: 100%; overflow: hidden; }
    body {
      background: #0b0e13;
      color: #e6e6e6;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      margin: 0;
      padding: 0;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
    }
    header { 
      padding: 1vh 2vw; 
      border-bottom: 1px solid #1f2430; 
      display: flex; 
      align-items: center; 
      gap: 12px; 
      flex-shrink: 0;
      height: 10vh;
    }
    .back-btn {
      background: #333;
      color: white;
      text-decoration: none;
      padding: 1vh 2vw;
      border-radius: 4px;
      font-size: 2vh;
      margin-right: 2vw;
    }
    h1 { font-size: 4vh; margin: 0; }
    main { 
      flex-grow: 1; 
      padding: 2vh; 
      display: grid; 
      grid-template-columns: 1fr 1fr 1fr; 
      grid-template-rows: 1fr 1fr; 
      gap: 2vh; 
    }
    .card {
      background: #131826;
      border-radius: 12px;
      padding: 2vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      position: relative;
    }
    .card-title {
      font-size: 2.5vh;
      color: #9fb0ff;
      margin-bottom: 2vh;
      text-transform: uppercase;
      letter-spacing: 1px;
    }
    .value-display {
      font-size: 5vh;
      color: #ffd28a;
      font-weight: bold;
      cursor: pointer;
      padding: 1vh 2vw;
      border: 1px solid #333;
      border-radius: 8px;
      background: #1a2030;
      min-width: 15vw;
      text-align: center;
    }
    .value-display:active { background: #252d40; }
    
    .btn-group { display: flex; gap: 1vw; }
    .toggle-btn {
      padding: 2vh 3vw;
      font-size: 2.5vh;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      background: #333;
      color: #888;
      font-weight: bold;
      transition: all 0.2s;
    }
    .toggle-btn.active {
      background: #3fdc5a;
      color: #000;
      box-shadow: 0 0 10px rgba(63, 220, 90, 0.4);
    }
    .toggle-btn.active-red {
        background: #ff4444;
        color: white;
        box-shadow: 0 0 10px rgba(255, 68, 68, 0.4);
    }

    /* Keypad Modal */
    #keypad-modal {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.8);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }
    .keypad {
      background: #1f2430;
      padding: 3vh;
      border-radius: 16px;
      display: flex;
      flex-direction: column;
      gap: 2vh;
      width: 40vw;
    }
    .keypad-display {
      background: #0b0e13;
      color: #ffd28a;
      font-size: 5vh;
      padding: 2vh;
      text-align: right;
      border-radius: 8px;
      font-family: monospace;
    }
    .keys {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1.5vh;
    }
    .key {
      background: #333;
      color: white;
      border: none;
      padding: 2vh;
      font-size: 3vh;
      border-radius: 8px;
      cursor: pointer;
    }
    .key:active { background: #555; }
    .key-enter { background: #3fdc5a; color: black; }
    .key-clear { background: #ff4444; }
    .key-cancel { background: #777; }
    
  </style>
</head>
<body>
  <header>
    <a href="/" class="back-btn">← BACK</a>
    <h1>Controls</h1>
    <div class="small" style="margin-left:auto;" id="status">connecting...</div>
  </header>
  <main>
    <!-- 1. Bake Timer -->
    <div class="card">
      <div class="card-title">Bake Timer</div>
      <div class="value-display" onclick="openKeypad('B1_Bake_Time', 'Bake Timer (min)')" id="disp_B1_Bake_Time">--</div>
    </div>
    
    <!-- 2. Temp Setpoint -->
    <div class="card">
      <div class="card-title">Temp Setpoint</div>
      <div class="value-display" onclick="openKeypad('W00[15]', 'Setpoint (°F)')" id="disp_W00_15">--</div>
    </div>
    
    <!-- 3. Lights -->
    <div class="card">
      <div class="card-title">Lights</div>
      <div class="btn-group">
        <button class="toggle-btn" id="btn_lights_on" onclick="sendCmd('M[1].0', 1)">ON</button>
        <button class="toggle-btn" id="btn_lights_off" onclick="sendCmd('M[0].15', 1)">OFF</button>
      </div>
      <div style="margin-top: 1vh; font-size: 1.5vh; color: #777;">Status: <span id="status_lights">--</span></div>
    </div>
    
    <!-- 4. Mode -->
    <div class="card">
      <div class="card-title">Mode</div>
      <div class="btn-group">
        <div style="display:flex; flex-direction:column; align-items:center;">
          <button class="toggle-btn" id="btn_mode_auto" onclick="sendCmd('M[1].4', 1)">AUTO</button>
          <span style="font-size:1.5vh; color:#777; margin-top:0.5vh;">Restart Bake</span>
        </div>
        <div style="display:flex; flex-direction:column; align-items:center;">
          <button class="toggle-btn" id="btn_mode_manual" onclick="sendCmd('M[1].5', 1)">MANUAL</button>
          <span style="font-size:1.5vh; color:#777; margin-top:0.5vh;">End Bake</span>
        </div>
      </div>
    </div>
    
    <!-- 5. Cooldown Timer -->
    <div class="card">
      <div class="card-title">Cooldown Timer</div>
      <div class="value-display" onclick="openKeypad('TMR[6].PRE', 'Cooldown (min)')" id="disp_TMR_6_PRE">--</div>
    </div>
    
    <!-- 6. Spare -->
    <div class="card" style="opacity: 0.5;">
      <div class="card-title">Spare</div>
      <div style="font-size: 3vh; color: #555;">RESERVED</div>
    </div>
  </main>

  <!-- Keypad Modal -->
  <div id="keypad-modal">
    <div class="keypad">
      <div style="color: #ccc; font-size: 2vh;" id="kp-title">Edit Value</div>
      <div class="keypad-display" id="kp-display">0</div>
      <div class="keys">
        <button class="key" onclick="kpAdd(7)">7</button>
        <button class="key" onclick="kpAdd(8)">8</button>
        <button class="key" onclick="kpAdd(9)">9</button>
        <button class="key" onclick="kpAdd(4)">4</button>
        <button class="key" onclick="kpAdd(5)">5</button>
        <button class="key" onclick="kpAdd(6)">6</button>
        <button class="key" onclick="kpAdd(1)">1</button>
        <button class="key" onclick="kpAdd(2)">2</button>
        <button class="key" onclick="kpAdd(3)">3</button>
        <button class="key key-clear" onclick="kpClear()">CLR</button>
        <button class="key" onclick="kpAdd(0)">0</button>
        <button class="key key-enter" onclick="kpEnter()">ENT</button>
        <button class="key key-cancel" style="grid-column: span 3;" onclick="kpClose()">CANCEL</button>
      </div>
    </div>
  </div>

  <script>
    let currentTag = null;
    let currentValStr = "";
    const statusEl = document.getElementById('status');

    // SSE for live updates
    const ev = new EventSource("/stream");
    ev.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.values) updateUI(data.values);
        if (data.error) statusEl.textContent = "Error: " + data.error;
        else statusEl.textContent = "Online";
      } catch (err) {}
    };

    function updateUI(vals) {
      // Bake Timer (B1_Bake_Time)
      if (vals.B1_Bake_Time !== undefined) {
        document.getElementById('disp_B1_Bake_Time').textContent = parseFloat(vals.B1_Bake_Time).toFixed(1) + " min";
      }
      
      // Temp Setpoint (W00[15]) - scaled x100
      if (vals['W00[15]'] !== undefined) {
        document.getElementById('disp_W00_15').textContent = (vals['W00[15]'] / 100).toFixed(1) + " °F";
      }
      
      // Cooldown (TMR[6].PRE) - ms to min
      if (vals['TMR[6].PRE'] !== undefined) {
        let min = (vals['TMR[6].PRE'] / 60000).toFixed(1);
        document.getElementById('disp_TMR_6_PRE').textContent = min + " min";
      }
      
      // Lights (M[3].0 status)
      const lightsOn = vals['M[3].0'] === 1;
      document.getElementById('btn_lights_on').className = 'toggle-btn ' + (lightsOn ? 'active' : '');
      document.getElementById('btn_lights_off').className = 'toggle-btn ' + (!lightsOn ? 'active-red' : '');
      document.getElementById('status_lights').textContent = lightsOn ? "ON" : "OFF";
      
      // Mode (M[1].4 Auto, M[1].5 Manual)
      const isAuto = vals['M[1].4'] === 1;
      const isManual = vals['M[1].5'] === 1;
      document.getElementById('btn_mode_auto').className = 'toggle-btn ' + (isAuto ? 'active' : '');
      document.getElementById('btn_mode_manual').className = 'toggle-btn ' + (isManual ? 'active' : '');
    }

    // Keypad Logic
    function openKeypad(tag, title) {
      currentTag = tag;
      currentValStr = "";
      document.getElementById('kp-title').textContent = title;
      document.getElementById('kp-display').textContent = "_";
      document.getElementById('keypad-modal').style.display = 'flex';
    }
    
    function kpClose() {
      document.getElementById('keypad-modal').style.display = 'none';
      currentTag = null;
    }
    
    function kpAdd(num) {
      if (currentValStr.length < 6) {
        currentValStr += num;
        document.getElementById('kp-display').textContent = currentValStr;
      }
    }
    
    function kpClear() {
      currentValStr = "";
      document.getElementById('kp-display').textContent = "_";
    }
    
    function kpEnter() {
      if (!currentTag || currentValStr === "") return;
      let val = parseFloat(currentValStr);
      
      // Conversions before sending
      if (currentTag === 'W16[1]' || currentTag === 'W00[15]') val = val * 100; // °F -> Scaled
      if (currentTag === 'TMR[6].PRE') val = val * 60000; // min -> ms
      
      sendCmd(currentTag, val);
      kpClose();
    }
    
    function sendCmd(tag, val) {
      fetch('/write', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tag: tag, value: val})
      }).catch(err => console.error("Write failed", err));
    }
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(PAGE, plc_ip=PLC_IP, poll_ms=int(POLL_SEC * 1000))

@app.route("/controls")
def controls():
    return render_template_string(CONTROLS_PAGE)

@app.route("/write", methods=["POST"])
def write_tag():
    try:
        data = request.json
        tag = data.get("tag")
        value = data.get("value")
        if not tag or value is None:
            return jsonify({"error": "Missing tag or value"}), 400
            
        with PLC() as comm:
            comm.IPAddress = PLC_IP
            # Determine type? pylogix usually handles it, but for REALs we might need to be careful.
            # B1_Bake_Time is REAL. W16_1 is INT. TMR_6_PRE is DINT.
            # pylogix Write should handle it if we pass the right python type.
            # value from JSON is likely float or int.
            
            res = comm.Write(tag, value)
            if res.Status != "Success":
                 return jsonify({"error": f"PLC Write Failed: {res.Status}"}), 500
                 
        return jsonify({"status": "ok", "tag": tag, "value": value})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/read")
def api_read():
    # One-shot read endpoint (for debugging, not strictly needed for SSE functionality)
    data = read_tags_once()
    return jsonify(data)

@app.route("/stream")
def stream():
    def gen():
        # Use a persistent PLC connection per client SSE stream
        while True:
            try:
                with PLC() as comm:
                    comm.IPAddress = PLC_IP
                    while True:
                        res = comm.Read(TAGS)
                        values = {}
                        for r in res:
                            if getattr(r, "Status", "") == "Success":
                                # For the bake timer, preserve one decimal (float). For others, cast to int.
                                if r.TagName == "B1_Bake_Time_ACC":
                                    try:
                                        values[r.TagName] = round(float(r.Value), 1)
                                    except Exception:
                                        values[r.TagName] = 0.0
                                else:
                                    try:
                                        values[r.TagName] = int(float(r.Value))
                                    except Exception:
                                        values[r.TagName] = 0
                            else:
                                values[r.TagName] = None
                        # Send the JSON payload for this update
                        payload = {"values": values}
                        yield f"data: {json.dumps(payload)}\n\n"
                        time.sleep(POLL_SEC)
            except Exception as e:
                # On error, send the error message then retry after a short delay
                err_msg = {"error": str(e).splitlines()[-1]}
                yield f"data: {json.dumps(err_msg)}\n\n"
                time.sleep(1.5)
    return Response(gen(), headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    })

@app.route("/health")
def health():
    return {"ok": True, "service": "booth-dashboard", "status": "online", "plc_ip": PLC_IP}

def read_tags_once():
    """Helper function to read all tags once (for /api/read or debugging)."""
    output = {"values": {}, "error": None}
    try:
        with PLC() as comm:
            comm.IPAddress = PLC_IP
            res = comm.Read(TAGS)
            for r in res:
                if getattr(r, "Status", "") == "Success":
                    if r.TagName == "B1_Bake_Time_ACC":
                        output["values"][r.TagName] = round(float(r.Value), 1)
                    else:
                        try:
                            output["values"][r.TagName] = int(float(r.Value))
                        except Exception:
                            output["values"][r.TagName] = 0
                else:
                    output["values"][r.TagName] = None
    except Exception as e:
        output["error"] = str(e).splitlines()[-1]
    return output

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
