from __future__ import annotations

from typing import Iterator
import requests
from config import ENCIRCLE_TOKEN, ENCIRCLE_BASE


class EncircleClient:
    def __init__(self, token: str = ENCIRCLE_TOKEN):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = self.session.get(f"{ENCIRCLE_BASE}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def list_property_claims(self, limit: int = 50, order: str = "newest") -> Iterator[dict]:
        cursor = None
        while True:
            params: dict = {"limit": limit, "order": order}
            if cursor:
                params["after"] = cursor
            data = self._get("/v1/property_claims", params)
            for claim in data.get("list", []):
                yield claim
            cursor = data.get("cursor", {}).get("after")
            if not cursor:
                return

    def get_property_claim(self, claim_id: int | str) -> dict:
        return self._get(f"/v1/property_claims/{claim_id}")

    def list_media(self, claim_id: int | str) -> list[dict]:
        items: list[dict] = []
        cursor = None
        while True:
            params: dict = {"limit": 100}
            if cursor:
                params["after"] = cursor
            data = self._get(f"/v1/property_claims/{claim_id}/media", params)
            items.extend(data.get("list", []))
            cursor = data.get("cursor", {}).get("after")
            if not cursor:
                return items
