#!/usr/bin/env python3
"""
Phase 1, part two. The first probe answered how deep the CC0 set is and
what a record looks like. The questions left are the ones that decide
whether this can work on e-ink at all:

  - can Smithsonian images be resized the way LOC's IIIF resizes, or are
    we stuck with whatever the collection happens to serve?
  - what share of CC0 records even use the resizable host?
  - which object types and which museums are worth offering as settings?

Prints structure and counts only, never the key.
"""

import json
import os
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
        print("  FAIL {} {}: {}".format(label or path, type(e).__name__, e))
    return None


def probe_image(url, label):
    """Fetch an image URL and report what came back, with pixel size."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "?")
    except urllib.error.HTTPError as e:
        print("    {:<34} HTTP {}".format(label, e.code))
        return
    except Exception as e:
        print("    {:<34} {}".format(label, type(e).__name__))
        return
    dims = "?"
    try:
        from PIL import Image
        import io
        dims = "{}x{}".format(*Image.open(io.BytesIO(raw)).size)
    except Exception:
        pass
    print("    {:<34} {:<12} {:>9}B  {}".format(label, ctype, len(raw), dims))


def media_of(row):
    return ((((row.get("content") or {}).get("descriptiveNonRepeating") or {})
             .get("online_media") or {}).get("media") or [])


def main():
    if not KEY:
        print("SI_API_KEY missing")
        return 1

    print("=== A. how many CC0 records use the resizable image host ===")
    hosts = Counter()
    arks = []
    units = Counter()
    types = Counter()
    for start in (0, 1000, 50000, 250000):
        d = api("/search", {"q": CC0, "rows": 100, "start": start},
                "sample at {}".format(start))
        rows = ((d or {}).get("response") or {}).get("rows") or []
        for r in rows:
            units[r.get("unitCode")] += 1
            idx = (r.get("content") or {}).get("indexedStructured") or {}
            for t in (idx.get("object_type") or []):
                types[t] += 1
            for m in media_of(r):
                ids_id = str(m.get("idsId") or "")
                hosts["ark (resizable)" if ids_id.startswith("ark:")
                      else "collections host" if "collections." in ids_id
                      else "other"] += 1
                if ids_id.startswith("ark:") and len(arks) < 4:
                    arks.append(ids_id)
        time.sleep(1)
    total = sum(hosts.values()) or 1
    for k, v in hosts.most_common():
        print("  {:<20} {:>5}  {:>3}%".format(k, v, round(100 * v / total)))
    print("\n  units in the sample : {}".format(units.most_common(12)))
    print("  object_type present : {}".format(types.most_common(15)))

    print("\n=== B. can we resize? ===")
    if not arks:
        print("  no ark-based image found in the sample")
    for ark in arks[:2]:
        print("  {}".format(ark))
        base = "https://ids.si.edu/ids/deliveryService/id/" + ark
        probe_image(base, "deliveryService (no size)")
        for size in (90, 400, 800, 1200):
            probe_image("{}/{}".format(base, size),
                        "deliveryService/{}".format(size))
        iiif = "https://ids.si.edu/iiif/" + ark
        probe_image(iiif + "/info.json", "iiif info.json")
        probe_image(iiif + "/full/!800,480/0/default.jpg", "iiif !800,480 colour")
        probe_image(iiif + "/full/!800,480/0/gray.jpg", "iiif !800,480 gray")
        print()

    print("=== C. how deep is each museum, CC0 with images ===")
    for unit in ("CHNDM", "SAAM", "NPG", "FSG", "NASM", "NMAH", "NMAfA",
                 "NMAI", "NPM", "SIL", "AAA", "HMSG", "ACM"):
        d = api("/search", {"q": '{} AND unit_code:"{}"'.format(CC0, unit),
                            "rows": 0}, unit)
        if d:
            print("  {:<8} {}".format(
                unit, ((d.get("response") or {}).get("rowCount"))))
        time.sleep(0.5)

    print("\n=== D. object types worth offering ===")
    for ot in ("Photographs", "Prints", "Drawings", "Paintings", "Sculpture",
               "Costume", "Furniture", "Aircraft", "Ceramic", "Textile",
               "Posters", "Books", "Jewelry", "Medals", "Models"):
        d = api("/search", {"q": '{} AND object_type:"{}"'.format(CC0, ot),
                            "rows": 0}, ot)
        if d:
            print("  {:<14} {}".format(
                ot, ((d.get("response") or {}).get("rowCount"))))
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
