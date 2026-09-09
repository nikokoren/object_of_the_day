#!/usr/bin/env python3
"""
Phase 1, part six. Three questions, one run.

  - Does the Postal Museum's CC0 set contain stamps at all? A 60-row
    sample was all covers and correspondence, and every object_type
    string I guessed returned zero, so the vocabulary has to be read off
    the records rather than assumed.
  - How do Air & Space and American History compare? Archival black and
    white is a different proposition from an object on grey seamless.
  - All three measured the same way, so the comparison means something.
"""

import io
import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

KEY = os.environ.get("SI_API_KEY", "")
BASE = "https://api.si.edu/openaccess/api/v1.0"
UA = "object-of-the-day/0.1 (github.com/nikokoren/object_of_the_day)"
CC0 = 'online_media_type:"Images" AND usage:"CC0"'


def api(params):
    params = dict(params)
    params["api_key"] = KEY
    url = "{}/search?{}".format(BASE, urllib.parse.urlencode(params))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as e:
        print("  FAIL {}".format(type(e).__name__))
    return None


def rows_for(unit, n=200):
    out = []
    for start in range(0, n, 100):
        d = api({"q": '{} AND unit_code:"{}"'.format(CC0, unit),
                 "rows": 100, "start": start})
        out += ((d or {}).get("response") or {}).get("rows") or []
        time.sleep(0.4)
    return out


def image_url(row, size=800):
    media = ((((row.get("content") or {}).get("descriptiveNonRepeating")
               or {}).get("online_media") or {}).get("media") or [])
    for m in media:
        content = str(m.get("content") or "")
        if "ids.si.edu" in content:
            return content + ("&" if "?" in content else "?") + "max=" + str(size)
    return None


def analyse(url):
    from PIL import Image, ImageFilter
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=45).read()
    rgb = Image.open(io.BytesIO(raw)).convert("RGB")
    if rgb.size[0] > 600:
        rgb = rgb.resize((600, max(1, int(600 * rgb.size[1] / rgb.size[0]))))
    grey = rgb.convert("L")
    px = list(grey.getdata())
    n = len(px) or 1
    ink = sum(1 for p in px if p < 90) / n
    paper = sum(1 for p in px if p > 200) / n
    edges = grey.filter(ImageFilter.FIND_EDGES).getdata()
    hsv = rgb.convert("HSV")
    hues = [p[0] for p in hsv.getdata() if p[1] > 60]
    warm = sum(1 for h in hues if h < 30 or h > 225) / max(len(hues), 1)
    return ((1 - ink - paper) * 100, sum(edges) / float(len(edges) or 1),
            100 * warm)


def main():
    if not KEY:
        return 1

    print("=== A. does the Postal Museum hold stamps ===")
    npm = rows_for("NPM", 200)
    types = Counter()
    for r in npm:
        idx = (r.get("content") or {}).get("indexedStructured") or {}
        for t in (idx.get("object_type") or []):
            types[t] += 1
    print("  object_type over {} rows:".format(len(npm)))
    for t, k in types.most_common(16):
        print("    {:>4}  {}".format(k, t))
    stampish = [t for t in types if "stamp" in t.lower()]
    print("  anything with 'stamp' in it: {}".format(stampish or "none"))
    for t in stampish[:4]:
        d = api({"q": '{} AND unit_code:"NPM" AND object_type:"{}"'.format(CC0, t),
                 "rows": 0})
        print("    {:<34} {}".format(
            t, ((d or {}).get("response") or {}).get("rowCount")))
        time.sleep(0.4)

    print("\n=== B. the three museums, measured the same way ===")
    for unit, label in (("NPM", "Postal Museum"),
                        ("NASM", "Air & Space"),
                        ("NMAH", "American History")):
        rows = npm if unit == "NPM" else rows_for(unit, 100)
        got, titles = [], []
        for r in rows:
            if len(got) >= 14:
                break
            url = image_url(r)
            if not url:
                continue
            try:
                got.append(analyse(url))
                titles.append(str(r.get("title"))[:46])
            except Exception:
                continue
            time.sleep(0.25)
        if not got:
            print("  {:<18} nothing measurable".format(label))
            continue
        print("  {:<18} n={:<3} mush {:>4.0f}  detail {:>4.0f}  warm {:>3.0f}%"
              .format(label, len(got),
                      statistics.median(g[0] for g in got),
                      statistics.median(g[1] for g in got),
                      statistics.median(g[2] for g in got)))
        best = sorted(range(len(got)), key=lambda i: -got[i][1])[:4]
        for i in best:
            print("      detail {:>4.0f}  mush {:>4.0f}  {}".format(
                got[i][1], got[i][0], titles[i]))
        types = Counter()
        for r in rows:
            idx = (r.get("content") or {}).get("indexedStructured") or {}
            for t in (idx.get("object_type") or []):
                types[t] += 1
        print("      types: {}".format(
            ", ".join("{} ({})".format(t, k) for t, k in types.most_common(6))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
