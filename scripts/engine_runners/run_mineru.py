#!/usr/bin/env python3
"""MinerU adapter over the persistent HTTP service.

Never invoke the `mineru` CLI per file: measured 6.4 s of interpreter+torch
import per call versus 0.03 s through this endpoint.
"""
import sys, requests
path, backend, url = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, "rb") as fh:
    r = requests.post(url + "/file_parse", files={"files": (path.split("/")[-1], fh)},
                      data={"backend": backend, "return_md": "true",
                            "return_content_list": "false", "return_images": "false"},
                      timeout=3600)
r.raise_for_status()
res = r.json()["results"]
sys.stdout.write(res[next(iter(res))].get("md_content", ""))
