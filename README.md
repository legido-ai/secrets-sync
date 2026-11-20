# secrets-sync

Fetches **named** secrets from OCI Vault and writes each one to a file, so a container can
consume a secret by mounting a directory instead of holding OCI credentials.

## Why it exists

On prod there are no long-lived credentials: no API keys, no static user. The instance principal
is obtained from the metadata service (IMDS) at `169.254.169.254`, and Gate 0 blocks IMDS for
bridged containers on purpose. This container therefore runs with **host networking** — one of the
two approved exceptions (`wireguard`, `secrets-sync`) — and is the only prod component allowed to
talk to IMDS. Constitution 5 and 44 record the trade: it holds the instance identity, so its IAM
grant is the real bound.

## Contract

| Variable | Meaning |
|---|---|
| `SECRETS` | `file_name=secret_ocid[,file_name=secret_ocid...]` |
| `OUT_DIR` | where files are written (default `/out`) |
| `REFRESH_SECONDS` | poll interval, minimum 30 (default 300) |
| `FILE_MODE` | file mode, default `0400` |

Writes are atomic (`tmp` + `rename`). On a failed refresh the previous file is left in place, so
consumers keep the last known good value. Secret content is never logged; only names, sizes and
errors.

## Deploy

```bash
docker compose -f secrets-sync.yml up -d
```

Pin the image by digest. No published ports, `read_only: true`, `cap_drop: [ALL]`,
`no-new-privileges`, `restart: unless-stopped`.

## IAM

The instance principal is granted `read secret-bundles` on the secrets it fetches, conditioned on
the private network source. Adding a secret means adding its OCID to `SECRETS` and tagging it in
the grant's condition — never a new user, key or broad policy.

## Build

`linux/arm64` by default (both OCI hosts are Arm). CI publishes on every push to `main`.
