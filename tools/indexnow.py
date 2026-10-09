#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tools/indexnow.py — tell the search engines about every URL in sitemap.xml.

IndexNow needs no account, no key from a vendor and no cost: you host a file
whose NAME is the key and whose CONTENT is the key, then POST the URL list and
point the engines at that file with `keyLocation`. The site lives on a subpath
of maxhemmerich.github.io, so the key file has to sit inside this project's own
subpath — nothing can be placed at the host root — and `keyLocation` is how the
engines are told where to find it:

    py -3.10 tools/indexnow.py --dry-run    # print the payload, send nothing
    py -3.10 tools/indexnow.py              # verify the key file is live, POST
    py -3.10 tools/indexnow.py --no-verify  # POST without the live key check

Re-run after ANY ship that adds or edits a page:

    py -3.10 tools/indexnow.py

The URL list is read straight out of the built sitemap.xml, so it cannot fall
out of step with the site: add a page, rebuild sitemap.xml, and it is submitted
here too. The key file never needs re-publishing; only the URL list changes.

The key is NEVER generated here. A new key means a new key file at a new URL,
which invalidates what engines have already seen — so the tool reads the key
that is already published at the repo root (the file's name and its content are
the same string) and refuses to run if it cannot find exactly one.

It prints the exact status code and body the endpoint returned — the record,
not a claim. It does not retry into a false success: a non-2xx is reported and
exits non-zero.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(TOOLS)          # the site root GitHub Pages serves
ENDPOINT = "https://api.indexnow.org/indexnow"
HOST = "maxhemmerich.github.io"
SITE = "https://%s/t776-rental-books" % HOST
SITEMAP = os.path.join(PROJECT, "sitemap.xml")
UA = "Mozilla/5.0 (compatible; DELTA-indexnow/1.0)"

# 200 = URLs accepted; 202 = accepted, key validation pending.
ACCEPTED = (200, 202)


def published_key():
    """The key already published at the repo root: a 32-hex .txt file whose
    content is its own name. Never generated, only read."""
    found = []
    for name in sorted(os.listdir(PROJECT)):
        m = re.fullmatch(r"([0-9a-fA-F]{8,128})\.txt", name)
        if not m:
            continue
        with open(os.path.join(PROJECT, name), encoding="utf-8") as fh:
            body = fh.read().strip()
        if body == m.group(1):
            found.append((m.group(1), name))
    if len(found) != 1:
        sys.exit("expected exactly one published IndexNow key file at %s, "
                 "found %d (%s) — refusing to guess"
                 % (PROJECT, len(found), [n for _k, n in found]))
    return found[0]


def sitemap_urls():
    with open(SITEMAP, encoding="utf-8") as fh:
        urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", fh.read())
    if not urls:
        sys.exit("sitemap.xml lists no URLs — nothing to submit")
    return urls


def verify_key_file(key_location, key):
    req = urllib.request.Request(key_location, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code, body = r.status, r.read().decode("utf-8", "replace").strip()
    except urllib.error.HTTPError as e:
        code, body = e.code, ""
    except Exception as e:  # noqa: BLE001
        print("  key-file check: no HTTP response (%s)" % e)
        return False
    ok = code == 200 and body == key
    print("  key file   : HTTP %s, body == the key: %s" % (code, ok))
    return ok


def main():
    dry = "--dry-run" in sys.argv
    no_verify = "--no-verify" in sys.argv

    key, key_file = published_key()
    urls = sitemap_urls()
    key_location = "%s/%s" % (SITE, key_file)

    print("IndexNow submission for %s" % SITE)
    print("  published key file : %s" % os.path.join(PROJECT, key_file))
    print("  key                : %s" % key)
    print("  keyLocation        : %s" % key_location)
    print("  urlList            : %d URLs from sitemap.xml" % len(urls))
    for u in urls:
        print("      %s" % u)

    if not no_verify and not dry:
        if not verify_key_file(key_location, key):
            sys.exit("the key file is not served as the key — refusing to POST "
                     "a submission the engines cannot validate")

    payload = {"host": HOST, "key": key, "keyLocation": key_location,
               "urlList": urls}
    if dry:
        print("\n--dry-run: payload only, nothing sent")
        print(json.dumps(payload, indent=2))
        return

    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": UA},
        method="POST")
    print("\nPOST %s" % ENDPOINT)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            code, text = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code, text = e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        print("  RESULT: no HTTP response (%s)" % e)
        sys.exit(1)

    print("  RESULT: HTTP %s" % code)
    print("  body: %r" % (text[:400],))
    if code in ACCEPTED:
        print("  VERDICT: the endpoint accepted the submission "
              "(%s = accepted, key validation pending)."
              % ("202" if code == 202 else "200"))
    else:
        print("  VERDICT: the endpoint did NOT accept it (see status above).")
        sys.exit(1)


if __name__ == "__main__":
    main()
