"""Fetch named secrets from OCI Vault and publish them as files for containers.

Identity: instance principal (IMDS). This container therefore runs with host
networking -- it is one of the two approved host-networked containers, and the
reason is that bridged containers cannot reach 169.254.169.254 (Constitution 44).

Contract:
  SECRETS        "file_name=secret_ocid[,file_name=secret_ocid...]"
  OUT_DIR        directory to write into (default /out)
  REFRESH_SECONDS  default 300, minimum 30
  FILE_MODE      default 0400

On refresh failure the previous file is left untouched, so consumers keep the
last known good value. Secret content is never logged.
"""

import base64
import os
import sys
import time

import oci
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner

OUT_DIR = os.environ.get("OUT_DIR", "/out")
REFRESH = max(30, int(os.environ.get("REFRESH_SECONDS", "300")))
MODE = int(os.environ.get("FILE_MODE", "0400"), 8)


def parse_secrets(raw):
    mapping = {}
    for item in filter(None, (part.strip() for part in raw.split(","))):
        name, sep, ocid = item.partition("=")
        if not sep or not name or not ocid.startswith("ocid1."):
            print("config error: expected name=ocid, got %r" % item[:20], flush=True)
            sys.exit(2)
        if "/" in name or name.startswith("."):
            print("config error: unsafe file name %r" % name, flush=True)
            sys.exit(2)
        mapping[name] = ocid
    if not mapping:
        print("config error: SECRETS is empty", flush=True)
        sys.exit(2)
    return mapping


def write_atomic(path, data):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, MODE)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(tmp, MODE)
    os.replace(tmp, path)


def main():
    mapping = parse_secrets(os.environ.get("SECRETS", ""))
    os.makedirs(OUT_DIR, exist_ok=True)
    signer = InstancePrincipalsSecurityTokenSigner()
    client = oci.secrets.SecretsClient({}, signer=signer)
    print("secrets-sync: %d secret(s) -> %s, refresh %ds" % (len(mapping), OUT_DIR, REFRESH), flush=True)

    while True:
        ok = 0
        for name, ocid in mapping.items():
            target = os.path.join(OUT_DIR, name)
            try:
                bundle = client.get_secret_bundle(ocid).data
                raw = base64.b64decode(bundle.secret_bundle_content.content)
                write_atomic(target, raw)
                ok += 1
                print("  %-24s ok (%d bytes)" % (name, len(raw)), flush=True)
            except Exception as exc:  # noqa: BLE001 - keep the last good file
                print("  %-24s FAILED: %s" % (name, type(exc).__name__), flush=True)
                if not os.path.exists(target):
                    print("    no previous value on disk for %s" % name, flush=True)
        print("cycle done: %d/%d" % (ok, len(mapping)), flush=True)
        time.sleep(REFRESH)


if __name__ == "__main__":
    main()
