#!/usr/bin/env python3
"""
Phase 1, part four. cat=art_design gives 82,319 CC0 objects with rich
metadata -- but none of the sampled records used the ark image host that
was verified as resizable. So: what image URLs do they actually carry,
and can any of those forms be asked for a given size?

Without an answer there is no recipe: an object photograph served at one
fixed size cannot be fitted to a panel.
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


def probe_image(url, label):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "?")
    except urllib.error.HTTPError as e:
        print("      {:<36} HTTP {}".format(label, e.code))
        return None
    except Exception as e:
        print("      {:<36} {}".format(label, type(e).__name__))
        return None
    dims = "?"
    try:
        from PIL import Image
        dims = "{}x{}".format(*Image.open(io.BytesIO(raw)).size)
    except Exception:
        pass
    print("      {:<36} {:<11} {:>8}B  {}".format(label, ctype, len(raw), dims))
    return raw


def score(raw):
    """The e-ink metric: mush, detail, texty."""
    from PIL import Image, ImageFilter
    im = Image.open(io.BytesIO(raw)).convert("L")
    if im.size[0] > 700:
        im = im.resize((700, int(700 * im.size[1] / im.size[0])))
    px = list(im.getdata())
    n = len(px) or 1
    ink = sum(1 for p in px if p < 90) / n
    paper = sum(1 for p in px if p > 200) / n
    edges = im.filter(ImageFilter.FIND_EDGES).getdata()
    return (round((1 - ink - paper) * 100, 1),
            round(sum(edges) / float(len(edges) or 1), 1))


def main():
    if not KEY:
        return 1

    print("=== A. what image URLs an art_design record carries ===")
    d = api("/category/art_design/search", {"q": CC0, "rows": 40})
    rows = ((d or {}).get("response") or {}).get("rows") or []
    forms = Counter()
    samples = []
    for r in rows:
        media = ((((r.get("content") or {}).get("descriptiveNonRepeating")
                   or {}).get("online_media") or {}).get("media") or [])
        for m in media:
            ids_id = str(m.get("idsId") or "")
            content = str(m.get("content") or "")
            if ids_id.startswith("ark:"):
                forms["idsId is an ark"] += 1
            elif "ids.si.edu" in content:
                forms["content on ids.si.edu"] += 1
            elif ids_id:
                forms["idsId: " + ids_id[:28]] += 1
            else:
                forms["no idsId"] += 1
            if len(samples) < 3:
                samples.append((r, m))
    print("  {}".format(forms.most_common(8)))
    for r, m in samples:
        print("\n  {}".format(str(r.get("title"))[:70]))
        print("    media json: {}".format(json.dumps(m)[:520]))

    print("\n=== B. can any of those forms be resized ===")
    for r, m in samples[:2]:
        print("  {}".format(str(r.get("title"))[:60]))
        content = str(m.get("content") or "")
        thumb = str(m.get("thumbnail") or "")
        ids_id = str(m.get("idsId") or "")
        probe_image(content, "content as given")
        probe_image(thumb, "thumbnail as given")
        for res in (m.get("resources") or []):
            probe_image(str(res.get("url")), str(res.get("label"))[:34])
        if ids_id and not ids_id.startswith("http"):
            for size in (400, 800, 1200):
                probe_image(
                    "https://ids.si.edu/ids/deliveryService?id={}&max={}".format(
                        ids_id, size), "deliveryService?id=&max={}".format(size))
        # the query-parameter form, which predates the ark paths
        if content and "id=" in content:
            for size in (400, 1200):
                probe_image(content + "&max=" + str(size),
                            "content + &max={}".format(size))
        print()

    print("=== C. does it survive a small grey panel ===")
    print("  {:>6} {:>7}  title".format("mush", "detail"))
    kept = []
    for r in rows[:14]:
        media = ((((r.get("content") or {}).get("descriptiveNonRepeating")
                   or {}).get("online_media") or {}).get("media") or [])
        if not media:
            continue
        url = str(media[0].get("content") or media[0].get("thumbnail") or "")
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            raw = urllib.request.urlopen(req, timeout=45).read()
            s = score(raw)
        except Exception:
            continue
        kept.append(s)
        print("  {:>6} {:>7}  {}".format(s[0], s[1], str(r.get("title"))[:52]))
        time.sleep(0.3)
    if kept:
        print("\n  median mush {:.0f}, median detail {:.0f}, n={}".format(
            statistics.median(s[0] for s in kept),
            statistics.median(s[1] for s in kept), len(kept)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
