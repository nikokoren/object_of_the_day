#!/usr/bin/env python3
"""
Phase 1, part five: the National Postal Museum.

Stamps are the best theoretical fit for e-ink in the whole collection --
line engraving at a tiny original size, scanned large, often printed in
two colours. This asks how many there are, what is known about each, and
whether they hold up on a small grey panel and on the black/white/red/
yellow one.
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
NPM = CC0 + ' AND unit_code:"NPM"'


def api(path, params=None):
    params = dict(params or {})
    params["api_key"] = KEY
    url = "{}{}?{}".format(BASE, path, urllib.parse.urlencode(params))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as e:
        print("  FAIL {} {}".format(path, type(e).__name__))
    return None


def count(q):
    d = api("/search", {"q": q, "rows": 0})
    return ((d or {}).get("response") or {}).get("rowCount")


def media_of(row):
    return ((((row.get("content") or {}).get("descriptiveNonRepeating")
              or {}).get("online_media") or {}).get("media") or [])


def image_url(row, size=800):
    for m in media_of(row):
        content = str(m.get("content") or "")
        if "ids.si.edu" in content:
            join = "&" if "?" in content else "?"
            return "{}{}max={}".format(content, join, size)
    return None


def analyse(url):
    """Grey legibility plus how the colour would map to a 4-colour panel."""
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
    mush = (1 - ink - paper) * 100
    edges = grey.filter(ImageFilter.FIND_EDGES).getdata()
    detail = sum(edges) / float(len(edges) or 1)
    hsv = rgb.convert("HSV")
    sat = [p[1] for p in hsv.getdata()]
    hues = [p[0] for p in hsv.getdata() if p[1] > 60]
    warm = sum(1 for h in hues if h < 30 or h > 225) / max(len(hues), 1)
    return (round(mush, 1), round(detail, 1),
            round(statistics.mean(sat), 1), round(100 * warm), rgb.size)


def main():
    if not KEY:
        return 1

    print("=== A. how many, and what kinds ===")
    print("  NPM, CC0 with images: {}".format(count(NPM)))
    for label, q in (
            ("  postage stamps", NPM + ' AND object_type:"Postage Stamps"'),
            ("  stamps (loose)", NPM + ' AND object_type:"Stamps"'),
            ("  covers/envelopes", NPM + ' AND object_type:"Covers"'),
            ("  essays & proofs", NPM + ' AND object_type:"Essays"'),
            ("  postal stationery", NPM + ' AND object_type:"Postal stationery"')):
        print("{:<22} {}".format(label, count(q)))
        time.sleep(0.4)

    d = api("/search", {"q": NPM, "rows": 60})
    rows = ((d or {}).get("response") or {}).get("rows") or []
    types, places, dates = Counter(), Counter(), Counter()
    for r in rows:
        idx = (r.get("content") or {}).get("indexedStructured") or {}
        for t in (idx.get("object_type") or []):
            types[t] += 1
        for p in (idx.get("place") or []):
            places[p] += 1
        for x in (idx.get("date") or []):
            dates[x] += 1
    print("\n  object_type in 60 rows: {}".format(types.most_common(8)))
    print("  places                : {}".format(places.most_common(6)))
    print("  dates                 : {}".format(dates.most_common(8)))

    print("\n=== B. what is known about one stamp ===")
    r = next((x for x in rows if image_url(x)), rows[0] if rows else None)
    if r:
        c = r.get("content") or {}
        idx = c.get("indexedStructured") or {}
        ft = c.get("freetext") or {}
        print("  title : {}".format(str(r.get("title"))[:90]))
        print("  id    : {}".format(r.get("id")))
        print("  link  : {}".format(
            str((c.get("descriptiveNonRepeating") or {}).get("record_link"))[:90]))
        for k in sorted(idx):
            print("  idx.{:<14}: {}".format(k, json.dumps(idx[k])[:130]))
        for k in sorted(ft):
            print("  ft.{:<15}: {}".format(k, json.dumps(ft[k])[:260]))
        print("  image : {}".format(image_url(r)))

    print("\n=== C. on a grey panel, and on the four-colour one ===")
    print("  {:>6} {:>7} {:>6} {:>6}  {:<14} title".format(
        "mush", "detail", "sat", "warm%", "size"))
    got = []
    for r in rows[:16]:
        url = image_url(r)
        if not url:
            continue
        try:
            mush, detail, sat, warm, size = analyse(url)
        except Exception:
            continue
        got.append((mush, detail, sat, warm))
        print("  {:>6} {:>7} {:>6} {:>5}%  {:<14} {}".format(
            mush, detail, sat, warm, "{}x{}".format(*size),
            str(r.get("title"))[:44]))
        time.sleep(0.3)
    if got:
        print("\n  median mush {:.0f}  detail {:.0f}  saturation {:.0f}  warm {:.0f}%"
              .format(statistics.median(g[0] for g in got),
                      statistics.median(g[1] for g in got),
                      statistics.median(g[2] for g in got),
                      statistics.median(g[3] for g in got)))
        print("  (warm% = share of saturated pixels that are red/orange/yellow,")
        print("   i.e. colour a black/white/red/yellow panel can actually show)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
