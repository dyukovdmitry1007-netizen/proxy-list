#!/usr/bin/env python3
"""
proxy_tool.py — proxy scraper + checker in one app.

Scrapes free proxies from multiple public sources, validates them
concurrently with asyncio, checks anonymity level, saves results.

Usage:
    python3 proxy_tool.py                     # scrape + check, save to ./proxies
    python3 proxy_tool.py -c 500              # concurrency 500
    python3 proxy_tool.py -t 8                # timeout 8s
    python3 proxy_tool.py --types http,socks4,socks5
    python3 proxy_tool.py --file mylist.txt   # check existing list instead of scraping
    python3 proxy_tool.py -o out/ -f json,txt

Output: alive.txt (ip:port), alive.json (with country/latency/anonymity),
grouped files: http.txt, socks4.txt, socks5.txt.
"""

import argparse
import asyncio
import json
import random
import re
import sys
import time
from pathlib import Path

import aiohttp

try:
    import aiohttp_socks
except ImportError:
    aiohttp_socks = None

# --------------------------------------------------------------------------
# Sources: each returns list of (protocol, ip, port)
# --------------------------------------------------------------------------

SOURCES = {
    # monosans — huge, all protocols, updated every few minutes
    "monosans": (
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.txt",
        "text",
    ),
    "monosans-socks4": (
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "text",
    ),
    "monosans-socks5": (
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "text",
    ),
    "monosans-http": (
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "text",
    ),
    # thespeedxxx — http/socks5 bundles
    "speedx-socks5": (
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "text",
    ),
    "speedx-http": (
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "text",
    ),
    "speedx-socks4": (
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "text",
    ),
    # proxyscrape API
    "proxyscrape-http": (
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "text",
    ),
    "proxyscrape-socks4": (
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4",
        "text",
    ),
    "proxyscrape-socks5": (
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5",
        "text",
    ),
    # clarketm list (mixed, mostly http)
    "clarketm": (
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "text",
    ),
    # shiftytr
    "shiftytr-socks5": (
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "text",
    ),
    # geonode API (paginated, first 2 pages)
    "geonode": ("GEONODE", "api"),
    # monosans https
    "monosans-https": (
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/https.txt",
        "text",
    ),
    # proxifly — 4 bundles
    "proxifly-http": (
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
        "text",
    ),
    "proxifly-https": (
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/https/data.txt",
        "text",
    ),
    "proxifly-socks4": (
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.txt",
        "text",
    ),
    "proxifly-socks5": (
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
        "text",
    ),
    # roosterkid
    "roosterkid-https": (
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "text",
    ),
    "roosterkid-socks5": (
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "text",
    ),
    # zevtyardt — big all-in-one
    "zevtyardt-all": (
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/all.txt",
        "text",
    ),
    # mmpx12
    "mmpx12-http": (
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
        "text",
    ),
    "mmpx12-socks4": (
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt",
        "text",
    ),
    "mmpx12-socks5": (
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
        "text",
    ),
    # jetkai
    "jetkai-http": (
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "text",
    ),
    "jetkai-socks4": (
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
        "text",
    ),
    "jetkai-socks5": (
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "text",
    ),
    # ShiftyTR additions
    "shiftytr-socks4": (
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        "text",
    ),
    "shiftytr-http": (
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "text",
    ),
    # sunny9577
    "sunny9577-http": (
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
        "text",
    ),
}

IPPORT_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{2,5})")
PROTOCOL_HINT_RE = re.compile(r"(socks5|socks4|https?)")


def infer_protocol(line: str, default="http"):
    m = PROTOCOL_HINT_RE.search(line)
    if m:
        p = m.group(1)
        return "https" if p == "https" else p
    return default


async def fetch_text(session, url, timeout):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            if r.status != 200:
                return []
            text = await r.text(errors="ignore")
            return [
                (None, m.group(1), int(m.group(2)))
                for m in IPPORT_RE.finditer(text)
            ]
    except Exception:
        return []


async def fetch_geonode(session, timeout, pages=2):
    out = []
    for page in range(1, pages + 1):
        url = (
            "https://proxylist.geonode.com/api/proxy-list"
            f"?limit=500&page={page}&sort_by=lastChecked&sort_type=desc"
        )
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status != 200:
                    continue
                data = await r.json(content_type=None)
                for p in data.get("data", []):
                    proto = "http"
                    if "socks5" in p.get("protocols", []):
                        proto = "socks5"
                    elif "socks4" in p.get("protocols", []):
                        proto = "socks4"
                    out.append((proto, p["ip"], int(p["port"])))
        except Exception:
            continue
    return out


async def scrape_all(timeout):
    """Pull from every source concurrently, return dict[(proto, ip, port)]."""
    results = {}
    async with aiohttp.ClientSession(
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    ) as session:
        tasks = {}
        for name, (url, kind) in SOURCES.items():
            if kind == "text":
                tasks[name] = fetch_text(session, url, timeout)
        tasks["geonode"] = fetch_geonode(session, timeout)

        done = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for name, res in zip(tasks.keys(), done):
            if isinstance(res, Exception) or not res:
                print(f"  [-] {name}: empty/failed")
                continue
            for proto, ip, port in res:
                if proto is None:
                    # monosans mixed file: lines tagged socks5://... — we parsed raw
                    # ip:port; re-derive protocol from source name
                    proto = infer_protocol(name, "http")
                    if "socks5" in name:
                        proto = "socks5"
                    elif "socks4" in name:
                        proto = "socks4"
                    elif "http" in name:
                        proto = "http"
                results.setdefault((proto, ip, port), name)
            print(f"  [+] {name}: {len(res)} proxies")
    return results


# --------------------------------------------------------------------------
# Checker
# --------------------------------------------------------------------------

JUDGE_URL = "http://ip-api.com/json/?fields=query,country,countryCode,proxy,hosting"

CHECK_TARGETS = [
    ("http", "http://ip-api.com/json/"),
    ("https", "https://httpbin.org/ip"),
]


async def check_proxy(sem, session, proto, ip, port, timeout, judge=True):
    """Return dict result for a proxy or None if dead."""
    proxy_url = f"{proto}://{ip}:{port}"
    async with sem:
        t0 = time.monotonic()
        try:
            # step 1: plain HTTP request through proxy (works for all types)
            resp = await session.get(
                "http://ip-api.com/json/?fields=query,country,countryCode,proxy,hosting",
                proxy=proxy_url if proto in ("http", "https") else None,
                timeout=aiohttp.ClientTimeout(total=timeout),
            )
            data = await resp.json(content_type=None)
            latency = round((time.monotonic() - t0) * 1000)
            real_ip = resp.headers.get("X-Real-IP")  # some proxies leak it
        except Exception:
            data = None
            real_ip = None
            # step 2: if aiohttp can't do socks natively, try aiohttp_socks
            if proto.startswith("socks") and aiohttp_socks:
                connector = aiohttp_socks.ProxyConnector.from_url(proxy_url)
                try:
                    async with aiohttp.ClientSession(connector=connector) as s2:
                        resp = await s2.get(JUDGE_URL, timeout=aiohttp.ClientTimeout(total=timeout))
                        data = await resp.json(content_type=None)
                        latency = round((time.monotonic() - t0) * 1000)
                except Exception:
                    return None
            else:
                return None

        if not isinstance(data, dict) or not data.get("query"):
            return None

        exit_ip = data.get("query", "")
        country = data.get("country", "?")
        cc = data.get("countryCode", "?")
        # anonymity: proxy flag + leaked ip vs exit ip
        flagged = bool(data.get("proxy"))
        anon = "transparent" if flagged else "anonymous"
        if real_ip and real_ip != exit_ip:
            anon = "transparent"

        return {
            "protocol": proto,
            "ip": ip,
            "port": port,
            "exit_ip": exit_ip,
            "country": country,
            "cc": cc,
            "latency_ms": latency,
            "anonymity": anon,
        }


async def run_check(proxies, concurrency, timeout):
    sem = asyncio.Semaphore(concurrency)
    # socks need the socks connector path; http/https go straight through aiohttp proxy=
    async with aiohttp.ClientSession() as session:
        tasks = [
            check_proxy(sem, session, p, i, po, timeout)
            for (p, i, po) in proxies
        ]
        results = []
        done = 0
        total = len(tasks)
        for fut in asyncio.as_completed(tasks):
            r = await fut
            done += 1
            if r:
                results.append(r)
            if done % 100 == 0 or done == total:
                alive = len(results)
                print(f"  checked {done}/{total} | alive: {alive}", end="\r")
        print()
    return results


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def save(results, outdir, formats):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    results.sort(key=lambda r: r["latency_ms"])

    if "json" in formats:
        (outdir / "alive.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False)
        )
    if "txt" in formats:
        (outdir / "alive.txt").write_text(
            "\n".join(f"{r['ip']}:{r['port']}" for r in results) + "\n"
        )
        # grouped by protocol
        for proto in ("http", "https", "socks4", "socks5"):
            grp = [r for r in results if r["protocol"] == proto]
            if grp:
                (outdir / f"{proto}.txt").write_text(
                    "\n".join(f"{r['ip']}:{r['port']}" for r in grp) + "\n"
                )
        # grouped by country
        countries = {}
        for r in results:
            countries.setdefault(r["cc"], []).append(f"{r['ip']}:{r['port']}")
        cdir = outdir / "by-country"
        cdir.mkdir(exist_ok=True)
        for cc, lines in countries.items():
            (cdir / f"{cc}.txt").write_text("\n".join(lines) + "\n")


def load_from_file(path):
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        proto = "http"
        if "://" in line:
            proto, rest = line.split("://", 1)
            line = rest
        m = IPPORT_RE.search(line)
        if m:
            out.append((proto, m.group(1), int(m.group(2))))
    return out


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Proxy scraper + checker")
    ap.add_argument("-c", "--concurrency", type=int, default=300)
    ap.add_argument("-t", "--timeout", type=int, default=8, help="seconds")
    ap.add_argument("--types", default="http,socks4,socks5",
                    help="comma list: http,https,socks4,socks5")
    ap.add_argument("-o", "--outdir", default="proxies")
    ap.add_argument("-f", "--formats", default="txt,json", help="txt,json")
    ap.add_argument("--file", help="check proxies from a local file instead of scraping")
    ap.add_argument("-n", "--max", type=int, default=0, help="max proxies to check (0=all)")
    args = ap.parse_args()

    wanted = {t.strip() for t in args.types.split(",")}

    print("[*] scraping sources...")
    if args.file:
        scraped = load_from_file(args.file)
        unique = {(p, i, po): "file" for (p, i, po) in scraped}
        print(f"  [+] file: {len(unique)} proxies")
    else:
        scraped = asyncio.run(scrape_all(args.timeout))
        unique = scraped

    # filter by type
    proxies = [(p, i, po) for (p, i, po) in unique if p in wanted]
    random.shuffle(proxies)
    if args.max:
        proxies = proxies[: args.max]
    print(f"[*] unique proxies to check: {len(proxies)}")

    if not proxies:
        print("[!] nothing to check")
        sys.exit(1)

    print(f"[*] checking (concurrency={args.concurrency}, timeout={args.timeout}s)...")
    t0 = time.monotonic()
    alive = asyncio.run(run_check(proxies, args.concurrency, args.timeout))
    dt = time.monotonic() - t0

    print(f"[*] alive: {len(alive)} / {len(proxies)} in {dt:.1f}s")
    save(alive, args.outdir, {f.strip() for f in args.formats.split(",")})
    print(f"[*] saved to {args.outdir}/")


if __name__ == "__main__":
    main()
