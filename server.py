from __future__ import annotations

import hmac
import logging
import os
import traceback
from flask import Flask, jsonify, request

from config import WEBHOOK_SECRET
from sync import SyncEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("encircle-sync")

app = Flask(__name__)
engine = SyncEngine(dry_run=False)


def _provided_secret(req) -> str:
    body = req.get_json(silent=True) or {}
    return (
        req.headers.get("X-Webhook-Secret")
        or req.headers.get("X-Webhook-Token")
        or req.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        or req.args.get("secret")
        or (body.get("secret") if isinstance(body, dict) else "")
        or ""
    )


def _authorized(req) -> bool:
    if not WEBHOOK_SECRET:
        log.warning("WEBHOOK_SECRET not set — refusing all requests")
        return False
    return hmac.compare_digest(_provided_secret(req), WEBHOOK_SECRET)


@app.get("/")
def health():
    return jsonify({"status": "ok", "service": "encircle-companycam-sync"})


@app.post("/webhook/encircle")
def webhook_encircle():
    if not _authorized(request):
        provided = _provided_secret(request)
        log.warning(
            "401: header_names=%s body_keys=%s provided_len=%d expected_len=%d",
            list(request.headers.keys()),
            list((request.get_json(silent=True) or {}).keys()) if request.is_json else "(not json)",
            len(provided),
            len(WEBHOOK_SECRET),
        )
        return jsonify({
            "error": "unauthorized",
            "hint": "send the secret as header X-Webhook-Secret, or include {\"secret\": \"...\"} in the JSON body",
            "received_header_names": sorted(request.headers.keys()),
            "received_body_keys": sorted((request.get_json(silent=True) or {}).keys()) if request.is_json else None,
            "provided_secret_length": len(provided),
            "expected_secret_length": len(WEBHOOK_SECRET),
        }), 401

    body = request.get_json(silent=True) or {}
    claim_id = body.get("claim_id") or request.args.get("claim_id")
    if not claim_id:
        return jsonify({"error": "missing claim_id in JSON body or query string"}), 400

    log.info("sync requested for claim_id=%s", claim_id)
    try:
        result = engine.sync_claim(claim_id)
    except Exception as e:
        log.error("sync failed for claim %s: %s\n%s", claim_id, e, traceback.format_exc())
        return jsonify({"error": str(e), "claim_id": str(claim_id)}), 500

    return jsonify({
        "claim_id": result.claim_id,
        "project_id": result.project_id,
        "project_created": result.project_created,
        "photos_total": result.photos_total,
        "photos_uploaded": result.photos_uploaded,
        "photos_skipped_existing": result.photos_skipped_existing,
        "photos_failed": result.photos_failed,
        "errors": result.errors,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
