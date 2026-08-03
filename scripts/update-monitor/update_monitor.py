#!/usr/bin/env python3
"""
update_monitor.py - Watch apt packages, GitHub releases (and optionally Docker
images) for updates, store findings in SQLite, notify via Pushover.

Usage:
  ./update_monitor.py check          # run all checkers, notify new items
  ./update_monitor.py list           # list unactioned items
  ./update_monitor.py done <guid>    # mark one item actioned
  ./update_monitor.py done-all       # mark ALL unactioned items actioned
  ./update_monitor.py test-notify    # send a test Pushover message
  ./reset_stale_notifications        # re-arm notifications for old unactioned items

Config: /etc/update-monitor.conf (or ./update-monitor.conf) - see example.
Cron:   0 8 * * * /usr/local/bin/update_monitor.py check
"""

import configparser
import json
import sqlite3
import subprocess
import sys
import urllib.request
import urllib.parse
import urllib.error
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- config ---

CONFIG_PATHS = [Path("/etc/update-monitor.conf"),
                Path(__file__).parent / "update-monitor.conf"]

SOURCES = ["apt", "system", "github", "docker"]

def load_config():
    cfg = configparser.ConfigParser()
    for p in CONFIG_PATHS:
        if p.exists():
            cfg.read(p)
            return cfg
    sys.exit("No config file found (looked for: "
             + ", ".join(str(p) for p in CONFIG_PATHS) + ")")


# -------------------------------------------------------------- database ---

SCHEMA = """
CREATE TABLE IF NOT EXISTS updates (
    guid        TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    system      TEXT NOT NULL,
    source      TEXT NOT NULL,
    subject     TEXT NOT NULL,
    description TEXT,
    unique_key  TEXT NOT NULL UNIQUE,
    actioned    INTEGER DEFAULT 0,
    notified    INTEGER DEFAULT 0
);
"""


def get_db(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute(SCHEMA)
    return db


def add_finding(db, system, source, subject, description, unique_key):
    """Insert a finding; returns True if it was new."""
    cur = db.execute(
        "INSERT OR IGNORE INTO updates "
        "(guid, created_at, system, source, subject, description, unique_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()),
         datetime.now(timezone.utc).isoformat(timespec="seconds"),
         system, source, subject, description, unique_key))
    return cur.rowcount == 1


# -------------------------------------------------------------- checkers ---

def check_apt(db, cfg):
    """apt list --upgradable -> one row per pending package version."""
    new = 0
    try:
        out = subprocess.run(
            ["apt", "list", "--upgradable"],
            capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        print(f"[apt] check failed: {e}", file=sys.stderr)
        return 0

    for line in out.splitlines():
        # format: nginx/noble-updates 1.24.0-2ubuntu7.1 amd64 [upgradable from: 1.24.0-2ubuntu7]
        if "[upgradable from:" not in line:
            continue
        try:
            pkg = line.split("/")[0]
            new_ver = line.split()[1]
            old_ver = line.split("upgradable from:")[1].strip(" ]")
        except IndexError:
            continue
        key = f"apt:{pkg}:{new_ver}"
        if add_finding(db, cfg.get('general', 'system'), "apt", f"{pkg} {new_ver}",
                       f"{pkg}: {old_ver} -> {new_ver}", key):
            new += 1
    return new


def check_reboot_required(db, cfg):
    """Ubuntu drops this file when a reboot is pending (e.g. kernel update)."""
    flag = Path("/var/run/reboot-required")
    if not flag.exists():
        return 0
    pkgs = ""
    pkgs_file = Path("/var/run/reboot-required.pkgs")
    if pkgs_file.exists():
        pkgs = ", ".join(pkgs_file.read_text().split())
    # keyed by date so a lingering flag re-notifies daily rather than never
    key = f"reboot:{datetime.now(timezone.utc).date()}"
    return 1 if add_finding(db, cfg.get('general', 'system'), "system", "Reboot required",
                            f"Pending reboot ({pkgs or 'kernel/libs'})",
                            key) else 0


def check_github(db, cfg, repos, token=""):
    """Latest release tag per repo via the GitHub API (no auth needed for
    public repos, but a token avoids rate limits)."""
    new = 0
    for repo in repos:
        repo = repo.strip()
        if not repo:
            continue
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "update-monitor"})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                rel = json.load(r)
        except Exception as e:
            print(f"[github] {repo}: {e}", file=sys.stderr)
            continue
        tag = rel.get("tag_name")
        if not tag:
            continue
        name = rel.get("name") or tag
        key = f"github:{repo}:{tag}"
        if add_finding(db, cfg.get('general', 'system'), "github", f"{repo} {tag}",
                       f"New release '{name}' - {rel.get('html_url', '')}",
                       key):
            new += 1
    return new


def check_docker(db, cfg):
    """Optional lightweight check: flags local images whose remote tag has a
    different digest. Skips silently if docker isn't installed. For anything
    serious (private registries etc.) run DIUN instead."""
    if subprocess.run(["which", "docker"], capture_output=True).returncode:
        return 0
    new = 0
    try:
        out = subprocess.run(
            ["docker", "image", "ls",
             "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True, text=True, timeout=60).stdout
    except Exception as e:
        print(f"[docker] check failed: {e}", file=sys.stderr)
        return 0

    images = sorted({i for i in out.splitlines()
                     if i and "<none>" not in i})
    for image in images:
        try:
            # local digest
            local = subprocess.run(
                ["docker", "image", "inspect", image,
                 "--format", "{{index .RepoDigests 0}}"],
                capture_output=True, text=True, timeout=30).stdout.strip()
            if not local or "@" not in local:
                continue
            local_digest = local.split("@")[1]
            # remote digest (buildx handles auth/manifest lists)
            remote_out = subprocess.run(
                ["docker", "buildx", "imagetools", "inspect", image,
                 "--format", "{{json .Manifest.Digest}}"],
                capture_output=True, text=True, timeout=60).stdout.strip()
            remote_digest = remote_out.strip('"')
            if not remote_digest.startswith("sha256:"):
                continue
        except Exception:
            continue
        if remote_digest != local_digest:
            key = f"docker:{image}:{remote_digest[:19]}"
            if add_finding(db, cfg.get('general', 'system'), "docker", f"{image}",
                           f"New digest for {image} "
                           f"({local_digest[:19]} -> {remote_digest[:19]})",
                           key):
                new += 1
    return new


# -------------------------------------------------------------- pushover ---

def pushover(cfg, source, title, message, priority=0):
    data = urllib.parse.urlencode({
        "token": cfg[source]["app_token"],
        "user": cfg["pushover"]["user_key"],
        "title": title,
        "message": message[:1024],   # Pushover message limit
        "priority": priority,
    }).encode()
    req = urllib.request.Request(
        "https://api.pushover.net/1/messages.json", data=data)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("status") == 1
    except urllib.error.HTTPError as e:
        print(f"[pushover] {e}: {e.read().decode()}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"[pushover] failed to send: {e}", file=sys.stderr)
        return False


def notify_pending(db, cfg):
    rows_total = 0
    for source in SOURCES:
        rows = db.execute(
            "SELECT * FROM updates WHERE actioned = 0 AND notified = 0 AND source = :source "
            "ORDER BY subject",
            {"source": source}).fetchall()
        if not rows:
            continue
        lines = [f"• {r['description']}" for r in rows]
        msg = "\n".join(lines)
        extra = db.execute(
            "SELECT COUNT(*) c FROM updates WHERE actioned = 0 AND notified = 1 AND source = :source",
            {"source": source}
        ).fetchone()["c"]
        if extra:
            msg += f"\n({extra} older items still unactioned)"
        if pushover(cfg, source, f"{len(rows)} update(s) pending for {cfg.get('general', 'system', fallback='Unknown System')}", msg):
            db.executemany("UPDATE updates SET notified = 1 WHERE guid = ?",
                        [(r["guid"],) for r in rows])
            db.commit()
        rows_total += len(rows)
    return rows_total 

def reset_stale_notifications(db, cfg):
    """Re-arm notifications for unactioned items older than the per-source
    threshold, so they get re-detailed in the next Pushover."""
    reset = 0
    for source in SOURCES:
        days = cfg.getint("renotify", source, fallback=0)
        if days <= 0:
            continue  # 0 or missing = notify once only
        cur = db.execute(
            "UPDATE updates SET notified = 0 "
            "WHERE actioned = 0 AND notified = 1 AND source = :source "
            "AND created_at <= datetime('now', :offset)",
            {"source": source, "offset": f"-{days} days"})
        reset += cur.rowcount
    db.commit()
    return reset

# ------------------------------------------------------------------ main ---

def cmd_check(cfg, db):
    counts = {
        "apt": check_apt(db, cfg),
        "system": check_reboot_required(db, cfg),
        "github": check_github(
            db,
            cfg,
            cfg.get("github", "repos", fallback="").split(","),
            cfg.get("github", "token", fallback="")),
    }
    if cfg.getboolean("docker", "enabled", fallback=True):
        counts["docker"] = check_docker(db, cfg)
    db.commit()
    stale = reset_stale_notifications(db, cfg)
    sent = notify_pending(db, cfg)
    print(f"new: {counts}  re-armed: {stale}  notified: {sent}")

def cmd_list(db):
    rows = db.execute(
        "SELECT guid, created_at, source, subject FROM updates "
        "WHERE actioned = 0 ORDER BY created_at").fetchall()
    if not rows:
        print("Nothing pending. ✓")
        return
    for r in rows:
        print(f"{r['guid']}  {r['created_at']}  [{r['source']}] "
              f"{r['subject']}")


def cmd_done(db, guid):
    cur = db.execute(
        "UPDATE updates SET actioned = 1 WHERE guid LIKE ? AND actioned = 0",
        (guid + "%",))
    db.commit()
    print(f"{cur.rowcount} item(s) marked actioned")


def cmd_done_all(db):
    cur = db.execute("UPDATE updates SET actioned = 1 WHERE actioned = 0")
    db.commit()
    print(f"{cur.rowcount} item(s) marked actioned")

def main():
    cfg = load_config()
    db = get_db(cfg.get("general", "db_path",
                        fallback="/var/lib/update-monitor/updates.db"))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        cmd_check(cfg, db)
    elif cmd == "list":
        cmd_list(db)
    elif cmd == "done" and len(sys.argv) > 2:
        cmd_done(db, sys.argv[2])
    elif cmd == "done-all":
        cmd_done_all(db)
    elif cmd == "test-notify":
        ok = pushover(cfg, "apt",  "update-monitor", "Test notification ✓")
        print("sent" if ok else "failed")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
