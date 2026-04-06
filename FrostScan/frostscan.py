"""
FrostScan – Disk Space Analyzer
Génère un rapport HTML interactif et l'ouvre dans le navigateur.
"""

import os
import sys
import shutil
import json
import webbrowser
import tempfile
import threading
import time
from pathlib import Path


# ─── Config ───────────────────────────────────────────────────────────────────

MAX_ITEMS   = 300   # nb d'éléments max dans le rapport
SCAN_DEPTH  = 3     # profondeur max d'exploration automatique


# ─── Helpers ──────────────────────────────────────────────────────────────────

def format_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def get_folder_size(path):
    total = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
                    elif e.is_dir(follow_symlinks=False):
                        total += get_folder_size(e.path)
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return total


def scan_root(root, progress_cb=None):
    entries = []
    try:
        items = list(os.scandir(root))
    except (PermissionError, OSError):
        return entries

    for i, e in enumerate(items):
        if progress_cb:
            progress_cb(e.name, i, len(items))
        try:
            if e.is_symlink():
                continue
            if e.is_file(follow_symlinks=False):
                size = e.stat(follow_symlinks=False).st_size
                entries.append({"path": e.path, "name": e.name,
                                 "size": size, "is_dir": False, "children": []})
            elif e.is_dir(follow_symlinks=False):
                size = get_folder_size(e.path)
                entries.append({"path": e.path, "name": e.name,
                                 "size": size, "is_dir": True, "children": []})
        except (PermissionError, OSError):
            pass

    entries.sort(key=lambda x: x["size"], reverse=True)
    return entries[:MAX_ITEMS]


# ─── HTML Template ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>❄️ FrostScan</title>
<style>
  :root {
    --bg:     #0d0d0d;
    --bg2:    #151515;
    --bg3:    #1e1e1e;
    --accent: #4fc3f7;
    --acc2:   #0288d1;
    --text:   #e0e0e0;
    --muted:  #666;
    --red:    #ef5350;
    --orange: #ff9800;
    --green:  #66bb6a;
    --border: #2a2a2a;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; min-height: 100vh; }

  header { background: var(--bg2); padding: 18px 32px; display: flex; align-items: center; gap: 14px; border-bottom: 1px solid var(--border); }
  header h1 { font-size: 1.6rem; color: var(--accent); font-weight: 700; }
  header p  { color: var(--muted); font-size: .9rem; }

  .disk-bar-wrap { padding: 16px 32px; background: var(--bg2); border-bottom: 1px solid var(--border); }
  .disk-info     { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: .85rem; color: var(--muted); }
  .disk-track    { background: var(--bg3); border-radius: 6px; height: 14px; overflow: hidden; }
  .disk-fill     { height: 100%; border-radius: 6px; transition: width .6s; }

  .controls { padding: 12px 32px; display: flex; gap: 12px; align-items: center; background: var(--bg); border-bottom: 1px solid var(--border); }
  .controls input { background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 7px 12px; color: var(--text); font-size: .9rem; flex: 1; max-width: 320px; outline: none; }
  .controls input:focus { border-color: var(--accent); }
  .controls label { color: var(--muted); font-size: .85rem; }
  .controls select { background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 7px 10px; color: var(--text); font-size: .85rem; outline: none; }

  .breadcrumb { padding: 10px 32px; font-size: .85rem; color: var(--muted); }
  .breadcrumb span { color: var(--accent); cursor: pointer; }
  .breadcrumb span:hover { text-decoration: underline; }

  table { width: 100%; border-collapse: collapse; }
  thead th { background: var(--bg3); padding: 10px 16px; text-align: left; font-size: .8rem; color: var(--accent); letter-spacing: .05em; cursor: pointer; user-select: none; position: sticky; top: 0; }
  thead th:hover { background: var(--border); }
  tbody tr { border-bottom: 1px solid var(--border); transition: background .12s; cursor: pointer; }
  tbody tr:hover { background: var(--bg2); }
  td { padding: 10px 16px; font-size: .9rem; vertical-align: middle; }
  td.name { display: flex; align-items: center; gap: 10px; }
  td.name .icon { font-size: 1.1rem; }
  td.name .lbl { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 400px; }
  td.name .dir-lbl { color: var(--accent); }
  td.size { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
  td.type { color: var(--muted); font-size: .8rem; }
  td.bar  { width: 220px; }
  .bar-wrap { background: var(--bg3); border-radius: 4px; height: 8px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; }
  .pct-lbl { font-size: .75rem; color: var(--muted); margin-top: 2px; }

  .table-wrap { overflow-x: auto; padding: 0 20px 40px; }
  .empty { text-align: center; padding: 40px; color: var(--muted); }

  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: .7rem; }
  .badge.dir  { background: #0277bd33; color: var(--accent); }
  .badge.file { background: #2a2a2a; color: var(--muted); }

  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg2); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
</head>
<body>

<header>
  <div>
    <h1>❄️ FrostScan</h1>
    <p>Rapport généré le __DATE__ — __ROOT__</p>
  </div>
</header>

<div class="disk-bar-wrap">
  <div class="disk-info">
    <span>💾 __USED__ utilisés sur __TOTAL__</span>
    <span>__FREE__ libres (__PCT_FREE__%)</span>
  </div>
  <div class="disk-track">
    <div class="disk-fill" id="diskFill" style="width:__PCT__%;background:__FILLCOLOR__"></div>
  </div>
</div>

<div class="controls">
  <input id="search" type="text" placeholder="🔍 Filtrer par nom…" oninput="applyFilters()">
  <label>Trier par :
    <select id="sortBy" onchange="applyFilters()">
      <option value="size">Taille ↓</option>
      <option value="name">Nom</option>
      <option value="type">Type</option>
    </select>
  </label>
  <label>
    <select id="typeFilter" onchange="applyFilters()">
      <option value="all">Tout</option>
      <option value="dir">Dossiers seulement</option>
      <option value="file">Fichiers seulement</option>
    </select>
  </label>
  <span id="count" style="color:var(--muted);font-size:.85rem;margin-left:auto"></span>
</div>

<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th onclick="toggleSort('name')" style="width:45%">Nom ⇅</th>
      <th onclick="toggleSort('size')" style="width:12%;text-align:right">Taille ⇅</th>
      <th style="width:10%">Type</th>
      <th style="width:33%">% du total scanné</th>
    </tr>
  </thead>
  <tbody id="tbody"></tbody>
</table>
<p class="empty" id="empty" style="display:none">Aucun résultat.</p>
</div>

<script>
const RAW = __DATA__;
const TOTAL_SCANNED = __TOTAL_SCANNED__;

const COLORS = [
  "#4fc3f7","#0288d1","#0277bd","#01579b",
  "#66bb6a","#43a047","#ff9800","#fb8c00",
  "#ef5350","#e53935","#ab47bc","#7e57c2"
];

let sortKey = "size";
let sortAsc  = false;

function fmtSize(n) {
  const u = ["B","KB","MB","GB","TB"];
  for (const unit of u) { if (n < 1024) return n.toFixed(1)+" "+unit; n/=1024; }
  return n.toFixed(1)+" PB";
}

function applyFilters() {
  const q    = document.getElementById("search").value.toLowerCase();
  const type = document.getElementById("typeFilter").value;
  const sort = document.getElementById("sortBy").value;
  sortKey = sort;

  let data = RAW.filter(d => {
    if (q && !d.name.toLowerCase().includes(q)) return false;
    if (type === "dir"  && !d.is_dir)  return false;
    if (type === "file" &&  d.is_dir)  return false;
    return true;
  });

  data.sort((a,b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (sortKey === "size") return sortAsc ? va-vb : vb-va;
    return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
  });

  render(data);
}

function toggleSort(key) {
  if (sortKey === key) sortAsc = !sortAsc;
  else { sortKey = key; sortAsc = false; }
  document.getElementById("sortBy").value = key;
  applyFilters();
}

function render(data) {
  const tbody = document.getElementById("tbody");
  tbody.innerHTML = "";
  document.getElementById("empty").style.display = data.length ? "none" : "block";
  document.getElementById("count").textContent = data.length + " élément(s)";

  data.forEach((item, i) => {
    const pct = TOTAL_SCANNED > 0 ? (item.size / TOTAL_SCANNED * 100) : 0;
    const color = COLORS[i % COLORS.length];
    const icon  = item.is_dir ? "📁" : getIcon(item.name);
    const badge = item.is_dir
      ? '<span class="badge dir">Dossier</span>'
      : '<span class="badge file">Fichier</span>';

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="name">
        <span class="icon">${icon}</span>
        <span class="lbl ${item.is_dir ? 'dir-lbl' : ''}" title="${item.path}">${item.name}</span>
      </td>
      <td class="size">${fmtSize(item.size)}</td>
      <td class="type">${badge}</td>
      <td class="bar">
        <div class="bar-wrap"><div class="bar-fill" style="width:${Math.min(pct,100)}%;background:${color}"></div></div>
        <div class="pct-lbl">${pct.toFixed(1)}%</div>
      </td>`;
    tbody.appendChild(tr);
  });
}

function getIcon(name) {
  const ext = name.split(".").pop().toLowerCase();
  const map = {
    mp4:"🎬",mkv:"🎬",avi:"🎬",mov:"🎬",
    mp3:"🎵",flac:"🎵",wav:"🎵",
    jpg:"🖼",jpeg:"🖼",png:"🖼",gif:"🖼",webp:"🖼",
    zip:"📦",rar:"📦","7z":"📦",tar:"📦",gz:"📦",
    pdf:"📕",doc:"📄",docx:"📄",xls:"📊",xlsx:"📊",ppt:"📊",pptx:"📊",
    exe:"⚙️",msi:"⚙️",
    iso:"💿",img:"💿",
    py:"🐍",js:"🟨",html:"🌐",css:"🎨",
  };
  return map[ext] || "📄";
}

applyFilters();
</script>
</body>
</html>
"""


# ─── Main ──────────────────────────────────────────────────────────────────────

def choose_root():
    """Let user pick a drive / folder via simple CLI if no arg given."""
    if len(sys.argv) > 1:
        return sys.argv[1]

    print("\n❄️  FrostScan – Disk Analyzer\n")

    if sys.platform == "win32":
        import string
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        print("Lecteurs disponibles :")
        for i, d in enumerate(drives):
            try:
                usage = shutil.disk_usage(d)
                print(f"  [{i}] {d}  —  {format_size(usage.free)} libres / {format_size(usage.total)}")
            except Exception:
                print(f"  [{i}] {d}")
        choice = input("\nChoix (numéro ou chemin complet) : ").strip()
        try:
            return drives[int(choice)]
        except (ValueError, IndexError):
            return choice or drives[0]
    else:
        return input("Chemin à scanner (défaut /) : ").strip() or "/"


def main():
    root = choose_root()
    if not os.path.exists(root):
        print(f"❌  Chemin introuvable : {root}")
        sys.exit(1)

    print(f"\n⏳  Scan de  {root}  en cours …")
    t0 = time.time()

    scanned = [0]
    def progress(name, i, total):
        scanned[0] += 1
        print(f"\r   {i+1}/{total}  {name[:60]:<60}", end="", flush=True)

    entries = scan_root(root, progress_cb=progress)
    print(f"\n✅  {len(entries)} éléments  ({time.time()-t0:.1f}s)\n")

    # Disk usage
    try:
        usage = shutil.disk_usage(root)
        used, total_disk, free = usage.used, usage.total, usage.free
    except Exception:
        used = total_disk = free = 0

    pct_used = (used / total_disk * 100) if total_disk else 0
    pct_free = 100 - pct_used
    fill_color = "#ef5350" if pct_used > 85 else "#ff9800" if pct_used > 60 else "#66bb6a"

    total_scanned = sum(e["size"] for e in entries)

    import datetime
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    # Serialize entries
    data_json = json.dumps([{"name": e["name"], "path": e["path"],
                              "size": e["size"], "is_dir": e["is_dir"]}
                             for e in entries])

    html = (HTML_TEMPLATE
        .replace("__DATE__",       date_str)
        .replace("__ROOT__",       root)
        .replace("__USED__",       format_size(used))
        .replace("__TOTAL__",      format_size(total_disk))
        .replace("__FREE__",       format_size(free))
        .replace("__PCT_FREE__",   f"{pct_free:.1f}")
        .replace("__PCT__",        f"{pct_used:.1f}")
        .replace("__FILLCOLOR__",  fill_color)
        .replace("__DATA__",       data_json)
        .replace("__TOTAL_SCANNED__", str(total_scanned))
    )

    # Write to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html",
                                      prefix="frostscan_", mode="w", encoding="utf-8")
    tmp.write(html)
    tmp.close()

    print(f"📊  Rapport : {tmp.name}")
    print("🌐  Ouverture dans le navigateur…\n")
    webbrowser.open(f"file:///{tmp.name}")

    input("   [Appuie sur Entrée pour fermer FrostScan] ")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAnnulé.")
