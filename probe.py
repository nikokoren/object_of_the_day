#!/usr/bin/env python3
"""
Phase 1, part three. Two things left before the harvester can be written.

  - The cat parameter (art_design, history_culture, science_technology)
    should get us out of the natural-history specimens that dominate the
    5.25M CC0 records. Does it, and what do those records look like?
  - Does object photography survive a 1-bit panel at all? The maps
    project learned to measure that rather than assume it, so the same
    metric runs here on real objects before a line of harvester exists.
"""

import io
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

KEY = os.environ.get("SI_API_KEY", "")
BASE = "https://api.si.edu/openaccess/api/v1.0"
UA = "object-of-the-day/0.1 (github.com/nikokoren/object_of_the_day)"
CC0 = 'online_media_type:"Images" AND usage:"CC0"'


def api(path, params=None, label=""):
    params = dict(params or {})
    params["api_key"] = KEY
    url = "{}{}?{}".format(BASE, path, urllib.parse.urlencode(params))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        print("  FAIL {} HTTP {}".format(label or path, e.code))
    except Exception as e:
        print("  FAIL {} {}".format(label or path, type(e).__name__))
    return None


def ark_of(row):
    media = ((((row.get("content") or {}).get("descriptiveNonRepeating")
               or {}).get("online_media") or {}).get("media") or [])
    for m in media:
        ids_id = str(m.get("idsId") or "")
        if ids_id.startswith("ark:"):
            return ids_id
    return None


def render_score(ark, width=400):
    """The e-ink metric from the maps project: mush, detail, textiness."""
    url = "https://ids.si.edu/ids/deliveryService/id/{}/{}".format(ark, width)
    try:
        from PIL import Image, ImageFilter
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        raw = urllib.request.urlopen(req, timeout=45).read()
        im = Image.open(io.BytesIO(raw)).convert("L")
    except Exception:
        return None
    px = list(im.getdata())
    n = len(px) or 1
    ink = sum(1 for p in px if p < 90) / n
    paper = sum(1 for p in px if p > 200) / n
    mush = (1 - ink - paper) * 100
    edges = im.filter(ImageFilter.FIND_EDGES).getdata()
    detail = sum(edges) / float(len(edges) or 1)
    w, h = im.size
    load = im.load()
    rows = [sum(load[x, y] for x in range(0, w, 2)) / (w / 2) for y in range(h)]
    cols = [sum(load[x, y] for y in range(0, h, 2)) / (h / 2) for x in range(w)]
    ralt = statistics.mean(abs(rows[i + 1] - rows[i]) for i in range(len(rows) - 1))
    calt = statistics.mean(abs(cols[i + 1] - cols[i]) for i in range(len(cols) - 1))
    return round(mush, 1), round(detail, 1), round(ralt / max(calt, 0.01), 2)


def main():
    if not KEY:
        return 1

    print("=== A. does cat= narrow it, and how deep is each ===")
    for cat in ("art_design", "history_culture", "science_technology"):
        d = api("/category/{}/search".format(cat), {"q": CC0, "rows": 0}, cat)
        if d:
            print("  {:<20} {}".format(
                cat, ((d.get("response") or {}).get("rowCount"))))
        time.sleep(0.5)

    print("\n=== B. what an art_design record carries ===")
    d = api("/category/art_design/search", {"q": CC0, "rows": 60}, "art rows")
    rows = ((d or {}).get("response") or {}).get("rows") or []
    print("  {} rows".format(len(rows)))
    units, types, with_ark = Counter(), Counter(), 0
    for r in rows:
        units[r.get("unitCode")] += 1
        idx = (r.get("content") or {}).get("indexedStructured") or {}
        for t in (idx.get("object_type") or []):
            types[t] += 1
        if ark_of(r):
            with_ark += 1
    print("  units      : {}".format(units.most_common(8)))
    print("  types      : {}".format(types.most_common(12)))
    print("  with ark   : {}/{}".format(with_ark, len(rows)))
    if rows:
        r = next((x for x in rows if ark_of(x)), rows[0])
        c = r.get("content") or {}
        idx = c.get("indexedStructured") or {}
        ft = c.get("freetext") or {}
        print("\n  a record:")
        print("    title    : {}".format(str(r.get("title"))[:80]))
        print("    unit     : {}  id: {}".format(r.get("unitCode"), r.get("id")))
        print("    link     : {}".format(
            str((c.get("descriptiveNonRepeating") or {}).get("record_link"))[:90]))
        for k in ("object_type", "date", "name", "place", "topic", "culture"):
            if idx.get(k):
                print("    idx.{:<9}: {}".format(k, json.dumps(idx[k])[:110]))
        for k in ("name", "date", "notes", "physicalDescription", "objectRights",
                  "creditLine", "setName", "place"):
            if ft.get(k):
                print("    ft.{:<10}: {}".format(k, json.dumps(ft[k])[:200]))

    print("\n=== C. does object photography survive a 1-bit panel ===")
    print("  {:>6} {:>7} {:>6}  {:<28} title".format(
        "mush", "detail", "text", "unit / type"))
    scored = []
    for r in rows[:22]:
        ark = ark_of(r)
        if not ark:
            continue
        s = render_score(ark)
        if not s:
            continue
        idx = (r.get("content") or {}).get("indexedStructured") or {}
        ot = (idx.get("object_type") or ["?"])[0]
        scored.append(s)
        print("  {:>6} {:>7} {:>6}  {:<28} {}".format(
            s[0], s[1], s[2], "{}/{}".format(r.get("unitCode"), ot)[:28],
            str(r.get("title"))[:40]))
        time.sleep(0.3)
    if scored:
        good = [s for s in scored if s[0] < 45 and s[1] > 28 and s[2] < 2.5]
        print("\n  {}/{} pass the maps thresholds (mush<45, detail>28, text<2.5)"
              .format(len(good), len(scored)))
        print("  median mush {:.0f}, median detail {:.0f}".format(
            statistics.median(s[0] for s in scored),
            statistics.median(s[1] for s in scored)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
