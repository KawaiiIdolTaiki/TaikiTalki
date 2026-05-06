import os
import json
import time
import threading
import queue
import subprocess
import ctypes
import ctypes.wintypes
from flask import Flask
from flask_sock import Sock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ─────────────────────────────────────────────────────────────────
#  CONFIG  — edit these to match your setup      # i hardcorde my own setup gl to everyone else :smile
# ─────────────────────────────────────────────────────────────────

PORT         = 8071

# Line 21 — path to your Firefox executable      # dont ask for different browser
BROWSER_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"

# Lines 24-27 — window size and position (pixels)
WIN_WIDTH    = 420
WIN_HEIGHT   = 187
WIN_X        = 1500    # distance from left edge of screen
WIN_Y        = 800    # distance from top edge of screen

# ─────────────────────────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DUMPS_DIR   = os.path.join(BASE_DIR, "dumps")
EVENTS_FILE = os.path.join(BASE_DIR, "events.json")


# ─────────────────────────────────────────────────────────────────
#  LOAD EVENTS DATABASE
# ─────────────────────────────────────────────────────────────────

def load_events():
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
            print(f"[OK] Loaded {len(db)} events from events.json")
            return db
    except FileNotFoundError:
        print("[WARN] events.json not found - starting with empty database")
        return {}

events_db = load_events()


# ─────────────────────────────────────────────────────────────────
#  WEBSOCKET CLIENT MANAGEMENT
# ─────────────────────────────────────────────────────────────────

connected_clients = []
clients_lock = threading.Lock()

def broadcast(data: dict):
    msg = json.dumps(data)
    with clients_lock:
        for q in connected_clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass


# ─────────────────────────────────────────────────────────────────
#  FILE HELPERS
# ─────────────────────────────────────────────────────────────────

def get_two_newest_files():
    try:
        files = [
            os.path.join(DUMPS_DIR, f)
            for f in os.listdir(DUMPS_DIR)
            if f.endswith(".json")
        ]
        files.sort(key=os.path.getmtime, reverse=True)
        return files[:2]
    except Exception:
        return []

def pick_response_file(files):
    if not files:
        return None
    if len(files) == 1:
        return files[0]
    return max(files, key=os.path.getsize)

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = find_key(v, key)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = find_key(item, key)
            if result is not None:
                return result
    return None


# ─────────────────────────────────────────────────────────────────
#  CORE LOGIC
# ─────────────────────────────────────────────────────────────────

def process_file(filepath: str):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not read {filepath}: {e}")
        return

    event_array = find_key(data, "unchecked_event_array")
    if not event_array:
        return

    event        = event_array[0]
    story_id     = str(event.get("story_id", ""))
    choice_array = (event
                    .get("event_contents_info", {})
                    .get("choice_array", []))

    slot_values = {}
    for i, choice in enumerate(choice_array):
        slot_values[i + 1] = choice.get("select_index")

    print(f"[EVENT] story_id={story_id}  slot_values={slot_values}")

    db_entry = events_db.get(story_id)

    if db_entry:
        check_pos       = db_entry.get("check_position")
        outcomes        = db_entry.get("outcomes", {})
        found_value     = slot_values.get(check_pos)
        found_value_str = str(found_value) if found_value is not None else None
        result          = outcomes.get(found_value_str)

        print(f"[EVENT] check_pos={check_pos}  value={found_value}  result={result}")

        broadcast({
            "status":      "found",
            "story_id":    story_id,
            "event_name":  db_entry.get("event_name", f"Event {story_id}"),
            "check_pos":   check_pos,
            "found_value": found_value,
            "result":      result,
            "outcomes":    outcomes,
            "slot_values": slot_values,
            "notes":       db_entry.get("notes", ""),
        })
    else:
        broadcast({
            "status":      "unknown",
            "story_id":    story_id,
            "slot_values": slot_values,
        })


# ─────────────────────────────────────────────────────────────────
#  WATCHDOG
# ─────────────────────────────────────────────────────────────────

class DumpWatcher(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".json"):
            return
        time.sleep(0.05)
        files = get_two_newest_files()
        response_file = pick_response_file(files)
        if response_file:
            process_file(response_file)


# ─────────────────────────────────────────────────────────────────
#  ALWAYS ON TOP  (line 153)
#  Uses Windows API via ctypes to pin the Firefox window.
#  This is the only reliable always-on-top method — browser JS
#  cannot do this on its own.
# ─────────────────────────────────────────────────────────────────

def set_firefox_topmost(enable: bool) -> bool:
    """
    Finds all visible Firefox windows by class name (MozillaWindowClass)
    and sets or clears HWND_TOPMOST via SetWindowPos.
    Using class name is reliable regardless of window title or Firefox version.
    """
    try:
        user32         = ctypes.windll.user32
        HWND_TOPMOST   = ctypes.wintypes.HWND(-1)
        HWND_NOTOPMOST = ctypes.wintypes.HWND(-2)
        SWP_NOMOVE     = 0x0002
        SWP_NOSIZE     = 0x0001
        SWP_NOACTIVATE = 0x0010
        flags          = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

        found_handles = []

        CallbackType = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPARAM
        )

        def _enum_callback(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd):
                # Match by window class name — always "MozillaWindowClass" for Firefox
                class_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_buf, 256)
                if class_buf.value == "MozillaWindowClass":
                    # Log the window title so we can confirm which window was found
                    title_len = user32.GetWindowTextLengthW(hwnd)
                    title_buf = ctypes.create_unicode_buffer(title_len + 1)
                    user32.GetWindowTextW(hwnd, title_buf, title_len + 1)
                    print(f"[AOT] Found: '{title_buf.value}'")
                    found_handles.append(hwnd)
            return True

        cb = CallbackType(_enum_callback)
        user32.EnumWindows(cb, 0)

        insert_after = HWND_TOPMOST if enable else HWND_NOTOPMOST
        for hwnd in found_handles:
            user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags)

        status = "ON" if enable else "OFF"
        print(f"[AOT] {status} — applied to {len(found_handles)} window(s)")
        return len(found_handles) > 0

    except Exception as e:
        print(f"[WARN] Always-on-top failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────────
#  BROWSER LAUNCHER  (line 205)
#  Opens /launch which uses window.open() to create a correctly
#  sized and positioned popup, then closes itself.
# ─────────────────────────────────────────────────────────────────

def open_browser():                                  # line 211
    try:
        url = f"http://localhost:{PORT}/launch"
        subprocess.Popen([BROWSER_PATH, "--new-window", url])
        print(f"[OK] Firefox opened -> http://localhost:{PORT}")
    except FileNotFoundError:
        print(f"[WARN] Firefox not found at: {BROWSER_PATH}")
        print(f"[INFO] Open manually: http://localhost:{PORT}")
    except Exception as e:
        print(f"[WARN] Could not open browser: {e}")


# ─────────────────────────────────────────────────────────────────
#  FLASK
# ─────────────────────────────────────────────────────────────────

app  = Flask(__name__)
sock = Sock(app)


@app.route("/launch")                                # line 226
def launch_page():
    """
    Opens the real tool as a correctly sized popup via window.open(),
    then closes this tab. If the popup is blocked, it redirects instead.
    NOTE: Firefox must allow popups for localhost:8071.
          Allow it via: Preferences > Privacy > Block pop-up windows > Exceptions
    """
    return f"""<!DOCTYPE html>
@app.route("/static/<path:filename>")
def static_files(filename):
    return app.send_static_file(filename)
<html>
<head>
<style>
  body {{
    background:#09090f; color:#706878;
    font-family:'Segoe UI',sans-serif; font-size:13px;
    display:flex; flex-direction:column;
    align-items:center; justify-content:center;
    height:100vh; margin:0; gap:14px;
  }}
  .tip {{
    font-size:11px; color:#333; max-width:320px;
    text-align:center; line-height:1.6;
  }}
  a {{ color:#c9963a; }}
</style>
</head>
<body>
<p>Opening TaikiTalki…</p>
<p class="tip">
  If nothing opens, Firefox may be blocking the popup.<br>
  Click the blocked popup icon in the address bar and choose
  <b>Allow popups for localhost</b>, then refresh this page.<br><br>
  Or open directly:
  <a href="http://localhost:{PORT}/">http://localhost:{PORT}/</a>
</p>
<script>
var w = window.open(
  'http://localhost:{PORT}/',
  'TaikiTalki',
  'width={WIN_WIDTH},height={WIN_HEIGHT},left={WIN_X},top={WIN_Y},resizable=yes,scrollbars=no'
);
if (w) {{
  w.focus();
  setTimeout(function() {{ window.close(); }}, 600);
}}
</script>
</body>
</html>"""


@app.route("/")                                      # line 271
def index():
    return HTML


@app.route("/api/topmost/<int:enable>")              # line 275
def api_topmost(enable):
    ok = set_firefox_topmost(bool(enable))
    return json.dumps({"ok": ok})


@sock.route("/ws")
def websocket(ws):
    client_q = queue.Queue(maxsize=10)
    with clients_lock:
        connected_clients.append(client_q)
    try:
        while True:
            try:
                msg = client_q.get(timeout=25)
                ws.send(msg)
            except queue.Empty:
                ws.send(json.dumps({"type": "ping"}))
    except Exception:
        pass
    finally:
        with clients_lock:
            if client_q in connected_clients:
                connected_clients.remove(client_q)


# ─────────────────────────────────────────────────────────────────
#  UI HTML  (line 299)
# ─────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TaikiTalki</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700;900&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:         #09090f;
    --bg2:        #10101c;
    --gold:       #c9963a;
    --gold-light: #e8ba5c;
    --pink:       #d4628a;
    --good:       #4caf50;
    --bad:        #e53935;
    --neutral:    #5c6bc0;
    --text:       #ddd5c8;
    --text-dim:   #706878;
    --border:     rgba(201,150,58,0.25);
  }

  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }

  body {
    background: var(--bg);
    background-image:
      radial-gradient(ellipse 60% 40% at 15% 10%, rgba(201,150,58,0.06) 0%, transparent 60%),
      radial-gradient(ellipse 50% 50% at 85% 90%, rgba(212,98,138,0.05) 0%, transparent 60%);
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 5px 5px 5px;
  }


  /* footer — status left, AoT right */
  #footer {
    width: 100%;
    max-width: 520px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 3px;
    border-top: 1px solid var(--border);
    margin-top: 3px;
  }

  .status-pill {
    display: flex; align-items: center; gap: 7px;
    font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--text-dim);
  }
  .dot {
    width: 8px; height: 8px; border-radius: 50%; background: #333;
    transition: background 0.4s, box-shadow 0.4s;
  }
  .dot.on  { background: var(--good); box-shadow: 0 0 8px var(--good); }
  .dot.off { background: var(--bad); }

  /* always-on-top checkbox  line 363 */
  #aot-label {
    display: flex; align-items: center; gap: 6px;
    font-size: 0.7rem; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--text-dim); cursor: pointer; user-select: none;
  }
  #aot-label:hover { color: var(--text); }
  #aot-cb { cursor: pointer; accent-color: var(--gold); }
  #aot-label.active { color: var(--gold); }

  /* ── Card ── */
  .card {
    width: 100%; max-width: 520px;
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: 5px; padding: 5px 5px;
    position: relative; overflow: hidden; min-height: 130px;
  }
  .card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--gold), var(--pink), var(--gold));
  }

  /* ── Waiting ── */
  .waiting {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 1px 0; gap: 1px;
  }
  .waiting-horse { font-size: 1.9rem; animation: float 2.5s ease-in-out infinite; display:flex; justify-content:center; }
  @keyframes float {
    0%,100% { transform:translateY(0);    opacity:0.5; }
    50%      { transform:translateY(-6px); opacity:0.9; }
  }
  .waiting-text {
    font-size: 0.78rem; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--text-dim);
  }

  /* ── Event header ── */
  .event-meta {
    font-size: 0.62rem; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--text-dim); margin-bottom: 0px;
  }
  .event-name {
    font-family: 'Cinzel', serif; font-size: 1.15rem; font-weight: 700;
    color: var(--gold-light); line-height: 1.35; margin-bottom: 0px;
  }

  /* ── Unknown event ── */
  .unknown-banner {
    background: rgba(229,57,53,0.1); border: 1px solid rgba(229,57,53,0.35);
    border-radius: 3px; padding: 3px 3px; margin-bottom: 0px;
  }
  .unknown-banner .u-label {
    font-size: 0.85 rem; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--bad); margin-bottom: 0px;
  }
  .unknown-banner .u-id   { font-family:'Cinzel',serif; font-size 1.10rem; font-weight:700; color:#ef9a9a; }


  /* ── Choices ── */
  .choice {
    display:flex; align-items:center; gap:12px;
    padding:3px 10px; border-radius:5px; border:1px solid transparent;
  }
  .choice.good    { background:rgba(76,175,80,0.09);  border-color:rgba(76,175,80,0.35); }
  .choice.bad     { background:rgba(229,57,53,0.08);  border-color:rgba(229,57,53,0.25); }
  .choice.optimal {
    background:rgba(76,175,80,0.16); border-color:var(--good);
    box-shadow: 0 0 16px rgba(76,175,80,0.22);
  }
  .choice.unk     { background:rgba(92,107,192,0.08); border-color:rgba(92,107,192,0.28); }
  .choice.dim     { opacity:0.6; background:rgba(255,255,255,0.02); border-color:rgba(255,255,255,0.08); }

  .choice-num {
    width:30px; height:30px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:0.85rem; font-weight:700; flex-shrink:0;
  }
  .choice.good    .choice-num,
  .choice.optimal .choice-num { background:rgba(76,175,80,0.2);  color:#a5d6a7; }
  .choice.bad     .choice-num { background:rgba(229,57,53,0.2);  color:#ef9a9a; }
  .choice.unk     .choice-num { background:rgba(92,107,192,0.2); color:#9fa8da; }
  .choice.dim     .choice-num { background:rgba(255,255,255,0.05); color:#444; }

  .choice-body { flex:1; display:flex; flex-direction:column; gap:2px; }
  .choice-label { font-size:0.76rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; }
  .choice.optimal .choice-label,
  .choice.bad     .choice-label { font-size:0.9rem; }
  .choice.good    .choice-label,
  .choice.optimal .choice-label { color:#a5d6a7; }
  .choice.bad     .choice-label { color:#ef9a9a; }
  .choice.unk     .choice-label { color:#9fa8da; }
  .choice.dim     .choice-label { color:#333; }

  .choice-val { font-size:0.99rem; color:#aaa; letter-spacing:0.06em; }

  .badge {
    font-size:0.58rem; font-weight:700; padding:3px 8px; border-radius:4px;
    background:var(--good); color:#fff; letter-spacing:0.1em;
    text-transform:uppercase; flex-shrink:0;
  }

  /* ── Notes ── */
  .notes {
    margin-top:14px; padding:9px 12px 9px 13px;
    background:rgba(201,150,58,0.07);
    border-left:3px solid var(--gold); border-radius:0 7px 7px 0;
    font-size:0.8rem; color:var(--text-dim); line-height:1.55;
  }
  .notes b { color:var(--gold); margin-right:5px; font-size:0.62rem; letter-spacing:0.12em; text-transform:uppercase; }

  /* result tag on the checked slot */
  .result-tag {
    display: inline-block;
    font-size: 1.1rem;
    font-weight: 900;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 2px;
  }
  .result-good { color: #66bb6a; text-shadow: 0 0 12px rgba(102,187,106,0.6); }
  .result-bad  { color: #ef5350; text-shadow: 0 0 12px rgba(239,83,80,0.6); }

  .choice-val-right {
    font-size: 0.75rem; color: var(--text-dim);
    letter-spacing: 0.06em; flex-shrink: 0; align-self: center;
  }

  @keyframes fadeUp {
    from { opacity:0; transform:translateY(8px); }
    to   { opacity:1; transform:translateY(0); }
  }
  .fade-in { animation: fadeUp 0.2s ease forwards; }
</style>
</head>
<body>

<div class="card" id="card">
  <div class="waiting">
    <div class="waiting-horse"><img src="/static/waiting.png" style="width:auto;height:125px;"></div>
    <div class="waiting-text">Waiting for event…</div>
  </div>
</div>

<!-- footer: status + always on top on the same line -->
<div id="footer">
  <div class="status-pill">
    <div class="dot off" id="dot"></div>
    <span id="status-text">Connecting</span>
  </div>
  <label id="aot-label" title="Pins this window above all others (Windows only)">
    <input type="checkbox" id="aot-cb"> Always on top
  </label>
</div>

<script>
const card       = document.getElementById('card');
const dot        = document.getElementById('dot');
const statusText = document.getElementById('status-text');
const aotLabel   = document.getElementById('aot-label');

function setStatus(ok) {
  dot.className        = 'dot ' + (ok ? 'on' : 'off');
  statusText.textContent = ok ? 'Connected' : 'Reconnecting';
}

/* ── Always on top  line 485
   Calls /api/topmost/1 or /api/topmost/0 on the Python backend.
   Python uses Windows ctypes to set HWND_TOPMOST on Firefox. ── */
document.getElementById('aot-cb').addEventListener('change', function () {
  const enable = this.checked ? 1 : 0;
  aotLabel.classList.toggle('active', this.checked);
  fetch('/api/topmost/' + enable)
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        alert('Always on top failed — may not work on non-Windows systems.');
        this.checked = false;
        aotLabel.classList.remove('active');
      }
    })
    .catch(() => {});
});

/* ── Render  line 501 ── */
function render(data) {
  if (data.type === 'ping') return;

  const slots     = data.slot_values || {};
  const positions = Object.keys(slots).map(Number).sort((a, b) => a - b);
  const total     = positions.length;

  const posLabel = pos => {
    if (total <= 2) return pos === 1 ? 'Top option' : 'Bottom option';
    if (pos === 1)       return 'Top option';
    if (pos === total)   return 'Bottom option';
    return 'Middle option';
  };

  /* unknown event */
  if (data.status === 'unknown') {
    const rows = positions.map(pos => `
      <div class="choice unk">
        <div class="choice-num">${pos}</div>
        <div class="choice-body">
          <div class="choice-label">${posLabel(pos)}</div>
          <div class="choice-val">value: ${slots[pos]}</div>
        </div>
      </div>`).join('');

    card.innerHTML = `<div class="fade-in">
      <div class="unknown-banner">
        <div class="u-label">⚠ Unmapped Event</div>
        <div class="u-id">ID: ${data.story_id}</div>
      </div>
      <div class="choices">${rows}</div>
    </div>`;
    return;
  }

  /* known event */
  // non-checked slots are opposite colour to the result:
  // if result=good → checked=green, others=red
  // if result=bad  → checked=red,   others=green
  const otherCls = data.result === 'good' ? 'bad'
                 : data.result === 'bad'  ? 'optimal'
                 : 'unk';

  const rows = positions.map(pos => {
    const isChecked = pos === data.check_pos;
    const val       = slots[pos];
    const result    = isChecked ? (data.result || 'unknown') : '';
    const cls       = isChecked
      ? (data.result === 'good' ? 'optimal' : data.result === 'bad' ? 'bad' : 'unk')
      : otherCls;
    return `
      <div class="choice ${cls}">
        <div class="choice-num">${pos}</div>
        <div class="choice-body">
          <div class="choice-label">
            ${isChecked ? '★ ' : ''}${posLabel(pos)}
          </div>
          ${isChecked
            ? `<div class="result-tag ${data.result === 'good' ? 'result-good' : 'result-bad'}">${result.toUpperCase()}</div>`
            : `<div class="result-tag ${otherCls === 'bad' ? 'result-bad' : 'result-good'}">${otherCls === 'bad' ? 'BAD' : 'GOOD'}</div>`
          }
        </div>
        <div class="choice-val-right">value: ${val}</div>
      </div>`;
  }).join('');

  card.innerHTML = `<div class="fade-in">
    <div class="event-meta">Event #${data.story_id}</div>
    <div class="event-name">${data.event_name}</div>
    <div class="choices">${rows}</div>
    ${data.notes ? `<div class="notes"><b>Note</b>${data.notes}</div>` : ''}
  </div>`;
}

/* ── WebSocket with auto-reconnect  line 558 ── */
function connect() {
  const ws = new WebSocket('ws://localhost:8071/ws');
  ws.onopen    = ()  => setStatus(true);
  ws.onclose   = ()  => { setStatus(false); setTimeout(connect, 2000); };
  ws.onerror   = ()  => ws.close();
  ws.onmessage = (e) => { try { render(JSON.parse(e.data)); } catch (_) {} };
}
connect();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(DUMPS_DIR, exist_ok=True)

    observer = Observer()
    observer.schedule(DumpWatcher(), DUMPS_DIR, recursive=False)
    observer.start()
    print(f"[OK] Watching: {DUMPS_DIR}")
    print(f"[OK] Open Firefox manually if the window doesn't appear: http://localhost:{PORT}/launch")

    threading.Timer(1.5, open_browser).start()

    try:
        app.run(debug=False, threaded=True, port=PORT)
    finally:
        observer.stop()
        observer.join()