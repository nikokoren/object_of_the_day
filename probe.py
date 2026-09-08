#!/usr/bin/env python3
"""
Phase 1: find out what the Smithsonian Open Access API actually returns.

Runs inside GitHub Actions, where SI_API_KEY exists as a secret. Prints
structure and counts only -- never the key, and never a whole record.

Everything here is a question, not an assumption: each probe reports the
status it got, so a wrong guess about an endpoint teaches us the shape
rather than failing silently.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KEY = os.environ.get("SI_API_KEY", "")
BASE = "https://api.si.edu/openaccess/api/v1.0"
UA = "object-of-the-day/0.1 (github.com/nikokoren/object_of_the_day)"


def get(path, params=None, label=""):
    params = dict(params or {})
    params["api_key"] = KEY
    url = "{}{}?{}".format(BASE, path, urllib.parse.urlencode(params))
    shown = url.replace(KEY, "<key>") if KEY else url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8", "replace")
            limit = resp.headers.get("X-RateLimit-Limit")
            left = resp.headers.get("X-RateLimit-Remaining")
        print("  OK   {}  {}".format(label or path,
                                     "rate {}/{}".format(left, limit)
                                     if limit else ""))
        return json.loads(body)
    except urllib.error.HTTPError as e:
        print("  FAIL {}  HTTP {}  {}".format(label or path, e.code, shown))
        try:
            print("       " + e.read().decode("utf-8", "replace")[:200])
        except Exception:
            pass
    except Exception as e:
        print("  FAIL {}  {}: {}".format(label or path, type(e).__name__, e))
    return None


def main():
    if not KEY:
        print("SI_API_KEY is empty -- the secret is not reaching the job")
        return 1
    print("key present, length {}\n".format(len(KEY)))

    print("=== 1. does the CC0 + images filter work, and how deep is it ===")
    for q in ('online_media_type:"Images" AND usage:"CC0"',
              'online_media_type:Images AND usage:CC0',
              '*:*'):
        d = get("/search", {"q": q, "rows": 1}, "q=" + q[:44])
        if d:
            r = d.get("response") or {}
            print("       rowCount = {}".format(r.get("rowCount")))
        time.sleep(1)

    print("\n=== 2. what a record looks like ===")
    d = get("/search", {"q": 'online_media_type:"Images" AND usage:"CC0"',
                        "rows": 3}, "sample rows")
    rows = ((d or {}).get("response") or {}).get("rows") or []
    print("       got {} rows".format(len(rows)))
    if rows:
        r = rows[0]
        print("       top-level keys: {}".format(sorted(r.keys())))
        content = r.get("content") or {}
        print("       content keys  : {}".format(sorted(content.keys())))
        descr = (content.get("descriptiveNonRepeating") or {})
        print("       descriptive   : {}".format(sorted(descr.keys())))
        media = descr.get("online_media") or {}
        print("       online_media  : {}".format(json.dumps(media)[:600]))
        indexed = content.get("indexedStructured") or {}
        print("       indexed keys  : {}".format(sorted(indexed.keys())))
        for k in ("object_type", "topic", "unit_code", "date", "place", "usage"):
            if k in indexed:
                print("         {:<12} {}".format(k, json.dumps(indexed[k])[:120]))
        freetext = content.get("freetext") or {}
        print("       freetext keys : {}".format(sorted(freetext.keys())))
        print("       title         : {}".format(str(r.get("title"))[:90]))
        print("       unit          : {}".format(r.get("unitCode")))

    print("\n=== 3. what categories exist to offer as settings ===")
    for term in ("object_type", "topic", "unit_code", "culture", "date"):
        d = get("/terms/" + term, {"rows": 12}, "terms/" + term)
        if d:
            resp = d.get("response") or {}
            terms = resp.get("terms") or []
            print("       {} terms, first few: {}".format(
                len(terms), json.dumps(terms[:12])[:300]))
        time.sleep(1)

    print("\n=== 4. can we count objects per category (for depth) ===")
    for ot in ("Photographs", "Prints", "Drawings", "Sculpture", "Costume",
               "Ceramics", "Aircraft", "Fossils", "Coins", "Furniture"):
        d = get("/search", {"q": 'online_media_type:"Images" AND usage:"CC0" '
                                 'AND object_type:"{}"'.format(ot),
                            "rows": 0}, "object_type=" + ot)
        if d:
            print("       {:<14} {}".format(
                ot, ((d.get("response") or {}).get("rowCount"))))
        time.sleep(0.6)

    print("\n=== 5. image URLs and whether they resize like LOC's IIIF ===")
    if rows:
        for r in rows[:3]:
            media = (((r.get("content") or {}).get("descriptiveNonRepeating")
                      or {}).get("online_media") or {}).get("media") or []
            for m in media[:2]:
                print("       type={} thumb={}".format(
                    m.get("type"), str(m.get("thumbnail"))[:100]))
                print("         content={}".format(str(m.get("content"))[:120]))
                for res in (m.get("resources") or [])[:3]:
                    print("         resource: {} {}".format(
                        res.get("label"), str(res.get("url"))[:110]))
                idsid = m.get("idsId") or m.get("guid")
                print("         idsId={}".format(idsid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
