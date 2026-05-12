from __future__ import annotations

from typing import Iterator
import requests
from config import COMPANYCAM_TOKEN, COMPANYCAM_BASE


class CompanyCamClient:
    def __init__(self, token: str = COMPANYCAM_TOKEN):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> dict:
        r = self.session.request(method, f"{COMPANYCAM_BASE}{path}", timeout=60, **kwargs)
        if not r.ok:
            raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)
        return r.json() if r.content else {}

    def list_projects(self, per_page: int = 100) -> Iterator[dict]:
        page = 1
        while True:
            data = self._request("GET", "/projects", params={"page": page, "per_page": per_page})
            if not data:
                return
            for p in data:
                yield p
            if len(data) < per_page:
                return
            page += 1

    def create_project(
        self,
        name: str,
        address: dict | None = None,
        primary_contact: dict | None = None,
    ) -> dict:
        project: dict = {"name": name}
        if address:
            project["address"] = address
        if primary_contact:
            project["primary_contact"] = primary_contact
        return self._request("POST", "/projects", json={"project": project})

    def add_project_labels(self, project_id: str, labels: list[str]) -> list[dict]:
        return self._request(
            "POST",
            f"/projects/{project_id}/labels",
            json={"project": {"labels": labels}},
        )

    def update_project_notepad(self, project_id: str, notepad: str) -> dict:
        return self._request(
            "PUT",
            f"/projects/{project_id}/notepad",
            json={"notepad": notepad},
        )

    def add_photo_from_url(
        self,
        project_id: str,
        photo_url: str,
        captured_at: int,
        tags: list[str] | None = None,
    ) -> dict:
        photo: dict = {"uri": photo_url, "captured_at": captured_at}
        if tags:
            photo["tags"] = tags
        return self._request(
            "POST",
            f"/projects/{project_id}/photos",
            json={"photo": photo},
        )

    def upload_photo_bytes(
        self,
        project_id: str,
        filename: str,
        content: bytes,
        content_type: str,
        captured_at: int,
        tags: list[str] | None = None,
    ) -> dict:
        files = {"photo[image]": (filename, content, content_type)}
        data: dict = {"photo[captured_at]": str(captured_at)}
        if tags:
            for t in tags:
                data.setdefault("photo[tags][]", []).append(t)
        # Multipart upload — strip JSON Accept default
        return self._request(
            "POST",
            f"/projects/{project_id}/photos",
            files=files,
            data=data,
        )
