#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
#   DDOS BY AH  |  Web Load Test Engine  |  v1.3
#   Authorized targets only · Termux ready · No root needed
# ============================================================

import asyncio
import aiohttp
import os
import random
import signal
import sys
import time

# ---------------------------------------------------------------- colors ---
R   = "\033[1;31m"
G   = "\033[1;32m"
Y   = "\033[1;33m"
B   = "\033[1;34m"
M   = "\033[1;35m"
C   = "\033[1;36m"
W   = "\033[1;97m"
DIM = "\033[2m"
RS  = "\033[0m"

VERSION      = "1.3"
HARD_RPS_CAP = 500
HARD_CONC_CAP = 100

def clear():
    os.system("clear" if os.name != "nt" else "cls")

def typeline(text, color=W, delay=0.02):
    for ch in text:
        sys.stdout.write(color + ch + RS)
        sys.stdout.flush()
        time.sleep(delay)
    print()

# ------------------------------------------------------------------ header -
def banner():
    clear()
    print(f"{R}")
    print("  ╔══════════════════════════════════════════════╗")
    print(f"  ║          {W}D D O S   B Y   A H{R}                 ║")
    print("  ╚══════════════════════════════════════════════╝")
    print(f"{RS}")
    print(f"  {C}Web Load Test Engine{RS} {DIM}·{RS} {G}v{VERSION}{RS} {DIM}·{RS} {Y}Termux Ready{RS}")
    print(f"  {DIM}Authorized targets only — own it or get written permission{RS}")
    print(f"  {DIM}──────────────────────────────────────────────────────────{RS}\n")

# ------------------------------------------------------------- animations --
def boot_sequence():
    lines = [
        (f"  {C}[*]{RS} Loading engine modules...", 0.4),
        (f"  {C}[*]{RS} Calibrating scheduler...", 0.4),
        (f"  {G}[+]{RS} Engine ready.", 0.3),
    ]
    for text, pause in lines:
        typeline(text, W, 0.015)
        time.sleep(pause)

def matrix_intro(seconds=2.0):
    cols = 55
    glyphs = "01#$%&@!*+=<>"
    t0 = time.time()
    print(C + DIM)
    while time.time() - t0 < seconds:
        print("".join(random.choice(glyphs) if random.random() < 0.25 else " "
                      for _ in range(cols)))
        time.sleep(0.06)
    print(RS)

def launch_animation(target, rps, conc):
    print(f"  {Y}┌─[ LAUNCH CONFIG ]────────────────────────────┐{RS}")
    print(f"  {Y}│{RS} {C}Target{RS}      : {W}{target}{RS}")
    print(f"  {Y}│{RS} {C}Rate cap{RS}    : {W}{rps} req/s{RS}")
    print(f"  {Y}│{RS} {C}Workers{RS}     : {W}{conc}{RS}")
    print(f"  {Y}└──────────────────────────────────────────────┘{RS}\n")
    bar_len = 30
    for i in range(bar_len + 1):
        pct = int(100 * i / bar_len)
        bar = G + "█" * i + DIM + "░" * (bar_len - i) + RS
        sys.stdout.write(f"\r  {M}>> ARMING{RS} [{bar}] {pct:3d}%")
        sys.stdout.flush()
        time.sleep(0.04)
    print("\n")

def status_bar(pct, rps, ok, err, p95):
    bar_len = 24
    filled = int(bar_len * pct / 100)
    color = G if pct < 60 else (Y if pct < 85 else R)
    bar = color + "█" * filled + DIM + "░" * (bar_len - filled) + RS
    return (f"\r  [{bar}] {W}{pct:5.1f}%{RS}  "
            f"{C}rps:{W}{rps:<4d}{RS}  {G}ok:{W}{ok:<6d}{RS}  "
            f"{R}err:{W}{err:<5d}{RS}  {M}p95:{W}{p95:>4.0f}ms{RS}   ")

# ----------------------------------------------------------------- engine --
class Stats:
    def __init__(self):
        self.sent = self.ok = self.err = self.redir = 0
        self.latencies = []
        self.stop = False

    def record(self, status, lat):
        self.sent += 1
        self.latencies.append(lat)
        if 200 <= status < 300:
            self.ok += 1
        elif status in (301, 302, 307, 308):
            self.redir += 1
        else:
            self.err += 1

    def pct(self, p):
        if not self.latencies:
            return 0
        s = sorted(self.latencies)
        return s[min(len(s) - 1, int(len(s) * p / 100))]

async def worker(session, cfg, stats, interval, paths):
    i = 0
    while not stats.stop:
        url = cfg["target"].rstrip("/") + paths[i % len(paths)]
        i += 1
        t0 = time.perf_counter()
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=cfg["timeout"]),
                allow_redirects=False,
            ) as r:
                await r.read()
                stats.record(r.status, time.perf_counter() - t0)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            stats.sent += 1
            stats.err += 1
        await asyncio.sleep(max(0, interval - (time.perf_counter() - t0)))

async def run_engine(cfg, paths, stats, duration):
    interval = cfg["concurrency"] / cfg["rps"]
    conn = aiohttp.TCPConnector(limit=cfg["concurrency"])
    async with aiohttp.ClientSession(
        connector=conn,
        headers={"User-Agent": f"DDOS-BY-AH/{VERSION} (authorized load test)"},
    ) as session:
        tasks = [asyncio.create_task(worker(session, cfg, stats, interval, paths))
                 for _ in range(cfg["concurrency"])]
        t0, last = time.time(), 0
        while time.time() - t0 < duration and not stats.stop:
            await asyncio.sleep(1)
            rps = stats.sent - last
            last = stats.sent
            pct = 100 * (time.time() - t0) / duration
            sys.stdout.write(status_bar(pct, rps, stats.ok, stats.err, stats.pct(95) * 1000))
            sys.stdout.flush()
        stats.stop = True
        await asyncio.gather(*tasks, return_exceptions=True)
    print()

# ------------------------------------------------------------------- UI ----
def ask(prompt, default=None, cast=str, lo=None, hi=None):
    while True:
        raw = input(f"  {G}➜{RS} {W}{prompt}{RS}"
                    + (f" {DIM}[{default}]{RS}" if default is not None else "") + ": ").strip()
        if not raw and default is not None:
            raw = str(default)
        try:
            val = cast(raw)
            if lo is not None:
                val = max(lo, val)
            if hi is not None:
                val = min(hi, val)
            return val
        except ValueError:
            print(f"  {R}[!] Invalid value, try again.{RS}")

def main_menu():
    banner()
    boot_sequence()
    matrix_intro(1.8)
    banner()
    print(f"  {Y}┌─[ TARGET CONFIGURATION ]─────────────────────┐{RS}\n")

    target = ask("Target URL", "https://example.com")
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    duration  = ask("Duration (seconds)", 30, int, 1, 600)
    rps       = ask("Max req/s (cap 500)", 50, int, 1, HARD_RPS_CAP)
    conc      = ask("Concurrent workers (cap 100)", 20, int, 1, HARD_CONC_CAP)
    paths_raw = ask("Paths (comma separated)", "/")
    paths = [p.strip() if p.strip().startswith("/") else "/" + p.strip()
             for p in paths_raw.split(",") if p.strip()]

    banner()
    launch_animation(target, rps, conc)

    stats = Stats()
    signal.signal(signal.SIGINT, lambda s, f: setattr(stats, "stop", True))

    cfg = {"target": target, "rps": rps, "concurrency": conc, "timeout": 10.0}
    asyncio.run(run_engine(cfg, paths, stats, duration))

    # ------------------------------------------------------ results -------
    dur = max(duration, 0.01)
    print(f"\n  {G}══════════════════════════════════════════════{RS}")
    print(f"  {W}          DDOS BY AH — RESULTS               {RS}")
    print(f"  {G}══════════════════════════════════════════════{RS}")
    print(f"  {C}Target{RS}        : {W}{target}{RS}")
    print(f"  {C}Duration{RS}      : {W}{dur:.1f}s{RS}")
    print(f"  {C}Sent{RS}          : {W}{stats.sent}{RS}")
    print(f"  {G}Success (2xx){RS} : {W}{stats.ok}{RS}")
    print(f"  {Y}Redirects{RS}     : {W}{stats.redir}{RS}")
    print(f"  {R}Errors{RS}        : {W}{stats.err}{RS}")
    print(f"  {C}Avg RPS{RS}       : {W}{stats.sent / dur:.1f}{RS}")
    if stats.latencies:
        avg = sum(stats.latencies) / len(stats.latencies) * 1000
        print(f"  {M}Latency{RS}       : {W}avg {avg:.0f} | p50 {stats.pct(50)*1000:.0f}"
              f" | p95 {stats.pct(95)*1000:.0f} | p99 {stats.pct(99)*1000:.0f} ms{RS}")
    ratio = stats.err / max(stats.sent, 1)
    verdict = (G + "TARGET STABLE" if ratio < 0.05 else
               Y + "DEGRADATION DETECTED" if ratio < 0.30 else
               R + "SATURATION — CHECK CAPACITY")
    print(f"  {C}Verdict{RS}       : {verdict}{RS}")
    print(f"  {G}══════════════════════════════════════════════{RS}\n")

    if input(f"  {Y}Run another test? (y/n){RS}: ").strip().lower() == "y":
        main_menu()
    else:
        typeline("\n  [+] Session closed.", G, 0.02)

if __name__ == "__main__":
    main_menu()
