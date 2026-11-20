# secrets-sync: fetch named secrets from OCI Vault as files.
# Runs with host networking (IMDS for instance principal); see Constitution 44.
FROM python:3.12-slim

RUN pip install --no-cache-dir "oci==2.192.0" \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin sync

COPY sync.py /sync.py
RUN chmod 0555 /sync.py

USER 10001
ENTRYPOINT ["python", "/sync.py"]
