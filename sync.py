from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass

from encircle import EncircleClient
from companycam import CompanyCamClient
from store import SyncStore
from config import COMPANYCAM_PROJECT_LABEL, COMPANYCAM_COMPLETE_LABEL


def _iso_to_unix(s: str | None) -> int:
    if not s:
        return int(datetime.now(tz=timezone.utc).timestamp())
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return int(datetime.fromisoformat(s).timestamp())


def project_name_for_claim(claim: dict) -> str:
    parts: list[str] = []
    parts.append(claim.get("policyholder_name") or "(no name)")
    parts.append(claim.get("full_address") or "(no address)")
    parts.append(str(claim["id"]))
    parts.append("Bloque")
    return " - ".join(parts)


def address_for_claim(claim: dict) -> dict | None:
    addr = claim.get("full_address")
    if not addr:
        return None
    bits = [b.strip() for b in addr.split(",")]
    out: dict = {}
    if bits:
        out["street_address_1"] = bits[0]
    if len(bits) >= 2:
        out["city"] = bits[1]
    if len(bits) >= 3:
        out["state"] = bits[2].split()[0] if bits[2] else ""
    out["country"] = "US"
    return out


_LOSS_TYPE_LABELS = {
    "type_of_loss_water": "Water Damage",
    "type_of_loss_fire": "Fire Damage",
    "type_of_loss_mold": "Mold",
    "type_of_loss_wind": "Wind Damage",
    "type_of_loss_storm": "Storm Damage",
    "type_of_loss_hail": "Hail Damage",
    "type_of_loss_smoke": "Smoke Damage",
    "type_of_loss_sewage": "Sewage / Contamination",
    "type_of_loss_biohazard": "Biohazard",
    "type_of_loss_vandalism": "Vandalism",
    "type_of_loss_theft": "Theft",
    "type_of_loss_impact": "Impact",
    "type_of_loss_other": "Other",
}


def humanize_loss_type(raw: str | None) -> str | None:
    if not raw:
        return None
    return _LOSS_TYPE_LABELS.get(raw, raw.replace("type_of_loss_", "").replace("_", " ").title())


def primary_contact_for_claim(claim: dict) -> dict | None:
    name = claim.get("policyholder_name")
    email = claim.get("policyholder_email_address")
    phone = claim.get("policyholder_phone_number")
    if not (name or email or phone):
        return None
    contact: dict = {}
    if name:
        contact["name"] = name
    if email:
        contact["email_address"] = email
    if phone:
        contact["phone_number"] = phone
    return contact


def notepad_for_claim(claim: dict) -> str:
    lines: list[str] = []
    def add(label: str, value):
        if value:
            lines.append(f"{label}: {value}")
    add("Type of Loss", humanize_loss_type(claim.get("type_of_loss")))
    add("Date of Loss", claim.get("date_of_loss"))
    add("Date Claim Created", claim.get("date_claim_created"))
    lines.append("")
    add("Policyholder", claim.get("policyholder_name"))
    add("Email", claim.get("policyholder_email_address"))
    add("Phone", claim.get("policyholder_phone_number"))
    add("Address", claim.get("full_address"))
    lines.append("")
    add("Insurance Carrier", claim.get("insurance_company_name"))
    add("Policy Number", claim.get("policy_number"))
    add("Adjuster", claim.get("adjuster_name"))
    add("Broker/Agent", claim.get("broker_or_agent_name"))
    add("Project Manager", claim.get("project_manager_name"))
    if claim.get("loss_details"):
        lines.append("")
        lines.append("Loss Details:")
        lines.append(claim["loss_details"])
    lines.append("")
    lines.append("---")
    lines.append(f"Synced from Encircle claim #{claim['id']} — {claim.get('permalink_url', '')}".rstrip(" —"))
    return "\n".join(lines).strip()


def media_tags(media: dict) -> list[str]:
    tags = list(media.get("labels") or [])
    src_type = media.get("source", {}).get("type")
    if src_type == "ClaimRoomAfterPicture":
        tags.append("after")
    elif src_type == "ClaimRoomBeforePicture":
        tags.append("before")
    return tags


@dataclass
class SyncResult:
    claim_id: str
    project_id: str | None
    project_created: bool
    photos_total: int
    photos_uploaded: int
    photos_skipped_existing: int
    photos_failed: int
    errors: list[str]


class SyncEngine:
    def __init__(
        self,
        encircle: EncircleClient | None = None,
        companycam: CompanyCamClient | None = None,
        store: SyncStore | None = None,
        dry_run: bool = True,
    ):
        self.encircle = encircle or EncircleClient()
        self.companycam = companycam or CompanyCamClient()
        self.store = store or SyncStore()
        self.dry_run = dry_run

    def _ensure_project(self, claim: dict) -> tuple[str | None, bool]:
        claim_id = str(claim["id"])
        existing = self.store.get_project_for_claim(claim_id)
        if existing:
            return existing["companycam_project_id"], False

        name = project_name_for_claim(claim)
        addr = address_for_claim(claim)
        contact = primary_contact_for_claim(claim)

        if self.dry_run:
            print(f"  [dry-run] would create CompanyCam project: {name}")
            return None, True

        resp = self.companycam.create_project(name=name, address=addr, primary_contact=contact)
        project_id = str(resp["id"])
        project_url = resp.get("project_url")
        self.store.record_project_for_claim(claim_id, project_id, project_url)
        print(f"  + created CompanyCam project {project_id} ({project_url})")

        labels_to_apply = [l for l in (COMPANYCAM_PROJECT_LABEL, COMPANYCAM_COMPLETE_LABEL) if l]
        if labels_to_apply:
            try:
                self.companycam.add_project_labels(project_id, labels_to_apply)
                print(f"  + applied labels: {labels_to_apply}")
            except Exception as e:
                print(f"  ! failed to apply labels {labels_to_apply}: {e}")

        return project_id, True

    def _sync_project_notepad(self, project_id: str | None, claim: dict) -> None:
        if not project_id:
            return
        notepad = notepad_for_claim(claim)
        if self.dry_run:
            print(f"  [dry-run] would update notepad ({len(notepad)} chars)")
            return
        try:
            self.companycam.update_project_notepad(project_id, notepad)
            print(f"  + updated notepad ({len(notepad)} chars)")
        except Exception as e:
            print(f"  ! failed to update notepad: {e}")

    def _push_photo(self, project_id: str | None, claim_id: str, media: dict) -> tuple[bool, str | None]:
        src = media.get("source", {})
        src_type = src.get("type", "")
        src_id = str(src.get("primary_id", ""))
        captured = _iso_to_unix(media.get("primary_client_created") or media.get("primary_server_created"))
        tags = media_tags(media)

        if self.dry_run or project_id is None:
            print(f"    [dry-run] would upload {media['filename']} (captured {captured}, tags {tags})")
            return True, None

        resp = self.companycam.add_photo_from_url(
            project_id=project_id,
            photo_url=media["download_uri"],
            captured_at=captured,
            tags=tags,
        )
        photo_id = str(resp.get("id", ""))
        self.store.record_photo_synced(claim_id, src_type, src_id, photo_id)
        return True, photo_id

    def sync_claim(self, claim_id: int | str) -> SyncResult:
        claim = self.encircle.get_property_claim(claim_id)
        cid = str(claim["id"])
        print(f"\n[claim {cid}] {claim.get('policyholder_name') or '(no name)'}  {claim.get('full_address') or ''}")

        project_id, created = self._ensure_project(claim)
        self._sync_project_notepad(project_id, claim)

        media = self.encircle.list_media(cid)
        result = SyncResult(
            claim_id=cid,
            project_id=project_id,
            project_created=created,
            photos_total=len(media),
            photos_uploaded=0,
            photos_skipped_existing=0,
            photos_failed=0,
            errors=[],
        )

        print(f"  {len(media)} media items in Encircle")

        for m in media:
            src = m.get("source", {})
            src_type = src.get("type", "")
            src_id = str(src.get("primary_id", ""))

            if not src_id:
                result.photos_failed += 1
                result.errors.append(f"missing source.primary_id on {m.get('filename')}")
                continue

            if self.store.is_photo_synced(src_type, src_id):
                result.photos_skipped_existing += 1
                continue

            try:
                ok, _photo_id = self._push_photo(project_id, cid, m)
                if ok:
                    result.photos_uploaded += 1
                else:
                    result.photos_failed += 1
            except Exception as e:
                result.photos_failed += 1
                result.errors.append(f"{m.get('filename')}: {e}")
                print(f"    ! failed {m.get('filename')}: {e}")

        print(
            f"  done: {result.photos_uploaded} uploaded, "
            f"{result.photos_skipped_existing} already-synced, "
            f"{result.photos_failed} failed"
        )
        return result

    def sync_recent(self, max_claims: int = 25) -> list[SyncResult]:
        results: list[SyncResult] = []
        for i, claim in enumerate(self.encircle.list_property_claims(limit=50, order="newest")):
            if i >= max_claims:
                break
            try:
                results.append(self.sync_claim(claim["id"]))
            except Exception as e:
                print(f"  ! failed claim {claim['id']}: {e}")
        return results
