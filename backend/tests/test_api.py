"""Acceptance tests mapped to the required operational scenarios."""
import io
import time

from PIL import Image

from tests.conftest import create_character, upload_image


def _new_version(client, h_editor, ch, note="造型更新"):
    cur = next(v for v in ch["versions"] if v["id"] == ch["current_version_id"])
    r = client.post(
        f"/characters/{ch['id']}/versions",
        headers=h_editor,
        json={
            "appearance": cur["appearance"] + "（新增蓝挑染）",
            "tone": cur["tone"],
            "restrictions": cur["restrictions"],
            "change_note": note,
            "image_ids": [i["id"] for i in cur["images"]],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _script_with_char(client, h_editor, ch, mode="latest"):
    r = client.post("/scripts", headers=h_editor, json={"title": "测试剧本"})
    script = r.json()
    body = {"character_id": ch["id"], "pin_mode": mode}
    if mode == "pinned":
        body["pinned_version_id"] = ch["current_version_id"]
    r = client.post(f"/scripts/{script['id']}/characters", headers=h_editor, json=body)
    assert r.status_code == 201, r.text
    r = client.post(
        f"/scripts/{script['id']}/scenes",
        headers=h_editor,
        json={"code": "S1", "title": "第一场", "sort_order": 1},
    )
    assert r.status_code == 201
    return client.get(f"/scripts/{script['id']}", headers=h_editor).json()


def _line(client, h_editor, script, ch):
    r = client.post(
        "/lines",
        headers=h_editor,
        json={"scene_id": script["scenes"][0]["id"],
              "character_id": ch["id"], "content": "你好，旧时光。"},
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestPermissions:
    def test_unauthenticated_rejected(self, client):
        r = client.get("/characters")
        assert r.status_code == 401

    def test_viewer_cannot_write(self, client, h):
        r = client.post(
            "/characters",
            headers=h["viewer"],
            json={"name": "x", "slug": "x", "appearance": "", "tone": "", "restrictions": ""},
        )
        assert r.status_code == 403

    def test_editor_cannot_retire_or_revoke(self, client, h, helpers):
        ch = helpers.create_character(client, h["editor"])
        refs = client.get(f"/characters/{ch['id']}/references", headers=h["editor"]).json()
        r = client.post(
            f"/characters/{ch['id']}/retire",
            headers=h["editor"],
            json={"strategy": "soft_delete", "expected_ref_count": refs["total"]},
        )
        assert r.status_code == 403
        img = helpers.upload_image(client, h["editor"], name="lic.png")
        assert client.post(f"/images/{img['id']}/revoke", headers=h["editor"]).status_code == 403


class TestConcurrentEdit:
    def test_second_writer_gets_409(self, client, h, helpers):
        ch = helpers.create_character(client, h["editor"])
        payload = {"name": "编剧A改的名字", "expected_revision": ch["revision"]}
        r1 = client.patch(f"/characters/{ch['id']}", headers=h["editor"], json=payload)
        assert r1.status_code == 200, r1.text
        # Writer B still holds the stale revision number.
        r2 = client.patch(
            f"/characters/{ch['id']}",
            headers=h["editor"],
            json={"name": "编剧B改的名字", "expected_revision": ch["revision"]},
        )
        assert r2.status_code == 409
        assert "版本号" in r2.json()["detail"]


class TestLineReviewProtection:
    def test_latest_ref_lines_flagged_pinned_untouched(self, client, h, helpers):
        ch = helpers.create_character(client, h["editor"])
        # floating reference script
        floating = _script_with_char(client, h["editor"], ch, "latest")
        line = _line(client, h["editor"], floating, ch)
        # pinned reference script
        pinned = _script_with_char(client, h["editor"], ch, "pinned")
        pinned_line = _line(client, h["editor"], pinned, ch)

        for lid in (line["id"], pinned_line["id"]):
            r = client.post(f"/lines/{lid}/approve", headers=h["editor"])
            assert r.status_code == 200, r.text

        v2 = _new_version(client, h["editor"], ch)

        lines_f = client.get(f"/scripts/{floating['id']}/lines", headers=h["editor"]).json()
        fl = next(x for x in lines_f if x["id"] == line["id"])
        assert fl["needs_recheck"] is True
        # snapshot kept at old version, not silently moved
        assert fl["interpretation_snapshot"]["version_id"] != v2["id"]

        lines_p = client.get(f"/scripts/{pinned['id']}/lines", headers=h["editor"]).json()
        pl = next(x for x in lines_p if x["id"] == pinned_line["id"])
        assert pl["needs_recheck"] is False

        reviews = client.get("/reviews", headers=h["editor"]).json()
        assert any(rv["line_id"] == line["id"] for rv in reviews)
        assert all(rv["line_id"] != pinned_line["id"] for rv in reviews)

    def test_reapprove_clears_flag(self, client, h, helpers):
        ch = helpers.create_character(client, h["editor"])
        script = _script_with_char(client, h["editor"], ch, "latest")
        line = _line(client, h["editor"], script, ch)
        client.post(f"/lines/{line['id']}/approve", headers=h["editor"])
        v2 = _new_version(client, h["editor"], ch)
        flagged = next(x for x in client.get(f"/scripts/{script['id']}/lines", headers=h["editor"]).json()
                       if x["id"] == line["id"])
        assert flagged["needs_recheck"] is True
        r = client.post(f"/lines/{line['id']}/reapprove", headers=h["editor"])
        assert r.status_code == 200
        data = r.json()
        assert data["needs_recheck"] is False
        assert data["interpretation_snapshot"]["version_id"] == v2["id"]
        reviews = client.get("/reviews", headers=h["editor"]).json()
        assert all(rv["line_id"] != line["id"] or rv["status"] == "resolved" for rv in reviews)


class TestRetire:
    def _setup(self, client, h, helpers):
        ch = helpers.create_character(client, h["editor"], slug="old", name="旧角色")
        script = _script_with_char(client, h["editor"], ch, "pinned")
        line = _line(client, h["editor"], script, ch)
        client.post(f"/lines/{line['id']}/approve", headers=h["editor"])
        return ch, script, line

    def test_references_precheck(self, client, h, helpers):
        ch, script, line = self._setup(client, h, helpers)
        refs = client.get(f"/characters/{ch['id']}/references", headers=h["viewer"]).json()
        assert refs["pinned_script_refs"]["count"] == 1
        assert refs["approved_lines"]["count"] == 1
        assert refs["total"] >= 2
        assert refs["approved_lines"]["items"][0]["scene_code"] == "S1"

    def test_expected_ref_count_mismatch_rejected(self, client, h, helpers):
        ch, _, _ = self._setup(client, h, helpers)
        refs = client.get(f"/characters/{ch['id']}/references", headers=h["admin"]).json()
        r = client.post(
            f"/characters/{ch['id']}/retire",
            headers=h["admin"],
            json={"strategy": "soft_delete", "expected_ref_count": refs["total"] + 5},
        )
        assert r.status_code == 409

    def test_new_ref_after_retire_rejected(self, client, h, helpers):
        ch, script, _ = self._setup(client, h, helpers)
        refs = client.get(f"/characters/{ch['id']}/references", headers=h["admin"]).json()
        r = client.post(
            f"/characters/{ch['id']}/retire",
            headers=h["admin"],
            json={"strategy": "soft_delete", "expected_ref_count": refs["total"]},
        )
        assert r.status_code == 200, r.text
        r = client.post(
            f"/scripts/{script['id']}/characters",
            headers=h["editor"],
            json={"character_id": ch["id"], "pin_mode": "latest"},
        )
        assert r.status_code == 409

    def test_replace_strategy_migrates_refs(self, client, h, helpers):
        ch, script, line = self._setup(client, h, helpers)
        replacement = helpers.create_character(client, h["editor"], slug="new", name="新角色")
        refs = client.get(f"/characters/{ch['id']}/references", headers=h["admin"]).json()
        r = client.post(
            f"/characters/{ch['id']}/retire",
            headers=h["admin"],
            json={
                "strategy": "replace",
                "expected_ref_count": refs["total"],
                "replacement_character_id": replacement["id"],
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["migrated_script_refs"] == 1
        assert data["migrated_pins"] == 1
        assert data["preserved_approved_lines"] == 1
        # old char retired, reference now points to replacement
        detail = client.get(f"/scripts/{script['id']}", headers=h["viewer"]).json()
        assert detail["characters"][0]["character_id"] == replacement["id"]
        assert detail["characters"][0]["pinned_version_id"] == replacement["current_version_id"]
        migrated_lines = client.get(f"/scripts/{script['id']}/lines", headers=h["viewer"]).json()
        assert migrated_lines[0]["character_id"] == replacement["id"]
        assert migrated_lines[0]["needs_recheck"] is True


class TestCoverJobs:
    def _job(self, client, h, helpers, crop=None, force_fail=False):
        img = helpers.upload_image(client, h["editor"], name="src.png")
        ch = helpers.create_character(client, h["editor"], image_id=img["id"])
        crop = crop or {"x": 0.0, "y": 0.0, "width": 0.9, "height": 0.9,
                        "target_width": 256, "target_height": 256, "force_fail": force_fail}
        r = client.post(
            f"/characters/{ch['id']}/versions/{ch['current_version_id']}/cover-jobs",
            headers=h["editor"],
            json={"source_image_id": img["id"], "crop": crop},
        )
        assert r.status_code == 202, r.text
        return ch, img, r.json()

    def test_idempotent_create(self, client, h, helpers):
        ch, img, job1 = self._job(client, h, helpers)
        r = client.post(
            f"/characters/{ch['id']}/versions/{ch['current_version_id']}/cover-jobs",
            headers=h["editor"],
            json={"source_image_id": img["id"],
                  "crop": {"x": 0.0, "y": 0.0, "width": 0.9, "height": 0.9,
                           "target_width": 256, "target_height": 256, "force_fail": False}},
        )
        assert r.status_code == 202
        assert r.json()["id"] == job1["id"]

    def test_worker_success_and_stale_guard(self, client, h, helpers):
        ch, img, job1 = self._job(client, h, helpers)
        run = client.post("/cover-jobs/process", headers=h["admin"])
        assert run.status_code == 200 and run.json()["processed"] >= 1
        done = client.get(f"/characters/{ch['id']}/jobs", headers=h["viewer"]).json()
        assert done[0]["status"] == "succeeded"
        card = client.get(f"/characters/{ch['id']}", headers=h["viewer"]).json()
        assert card["active_cover_url"]

        # second, newer job enqueued and finished first
        r = client.post(
            f"/characters/{ch['id']}/versions/{ch['current_version_id']}/cover-jobs",
            headers=h["editor"],
            json={"source_image_id": img["id"],
                  "crop": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8,
                           "target_width": 256, "target_height": 256, "force_fail": False}},
        )
        job2 = r.json()
        client.post("/cover-jobs/process", headers=h["admin"])
        # Now simulate the old job being retried late: reset and reprocess it.
        # The stale guard compares request order, so the late old job must not
        # overwrite the newer cover.
        from app.database import SessionLocal
        from app.models import CoverJob

        db = SessionLocal()
        try:
            old = db.query(CoverJob).get(job1["id"])
            old.status = "pending"
            db.commit()
        finally:
            db.close()
        client.post("/cover-jobs/process", headers=h["admin"])
        db = SessionLocal()
        try:
            old = db.query(CoverJob).get(job1["id"])
            assert old.status == "stale"
            card2 = client.get(f"/characters/{ch['id']}", headers=h["viewer"]).json()
            new_job = db.query(CoverJob).get(job2["id"])
            assert card2["active_cover_url"] is not None
            assert new_job.result_asset_id is not None
        finally:
            db.close()

    def test_failed_job_creates_review(self, client, h, helpers):
        _ch, _img, job = self._job(client, h, helpers, force_fail=True)
        client.post("/cover-jobs/process", headers=h["admin"])
        jobs = client.get(f"/characters/{_ch['id']}/jobs", headers=h["viewer"]).json()
        assert jobs[0]["status"] == "failed"
        reviews = client.get("/reviews", headers=h["viewer"]).json()
        assert any(rv["kind"] == "cover_failed" and rv["job_id"] == job["id"] for rv in reviews)


class TestExports:
    def test_create_export(self, client, h, helpers):
        ch = helpers.create_character(client, h["editor"])
        script = _script_with_char(client, h["editor"], ch, "latest")
        line = _line(client, h["editor"], script, ch)
        client.post(f"/lines/{line['id']}/approve", headers=h["editor"])
        r = client.post(
            f"/scripts/{script['id']}/exports",
            headers=h["editor"],
            json={"label": "送审-1"},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["payload"]["script"]["id"] == script["id"]
        assert ch["current_version_id"] in data["payload"]["version_ids"]
        assert any(l["line_id"] == line["id"] for l in data["payload"]["lines"])


class TestLicenseRevoke:
    def test_revoke_cascades(self, client, h, helpers):
        img = helpers.upload_image(client, h["editor"], name="licensed.png")
        ch = helpers.create_character(client, h["editor"], image_id=img["id"])
        script = _script_with_char(client, h["editor"], ch, "latest")
        line = _line(client, h["editor"], script, ch)
        client.post(f"/lines/{line['id']}/approve", headers=h["editor"])
        r = client.post(f"/images/{img['id']}/revoke", headers=h["admin"])
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["image"]["license_status"] == "revoked"
        assert data["flagged_lines"] == 1
        assert ch["current_version_id"] in data["affected_versions"]
        # cannot derive new cover from revoked image
        r = client.post(
            f"/characters/{ch['id']}/versions/{ch['current_version_id']}/cover-jobs",
            headers=h["editor"],
            json={"source_image_id": img["id"],
                  "crop": {"x": 0, "y": 0, "width": 0.5, "height": 0.5,
                           "target_width": 128, "target_height": 128, "force_fail": False}},
        )
        assert r.status_code == 409
        flagged = next(x for x in client.get(f"/scripts/{script['id']}/lines", headers=h["viewer"]).json()
                       if x["id"] == line["id"])
        assert flagged["needs_recheck"] is True


class TestCleanup:
    def test_cleanup_permission(self, client, h, helpers):
        assert client.post("/admin/cleanup", headers=h["editor"]).status_code == 403
        r = client.post("/admin/cleanup?dry_run=true", headers=h["admin"])
        assert r.status_code == 200

    def test_export_snapshot_protects_assets(self, client, h, helpers):
        img = helpers.upload_image(client, h["editor"], name="keep.png")
        ch = helpers.create_character(client, h["editor"], image_id=img["id"])
        script = _script_with_char(client, h["editor"], ch, "latest")
        line = _line(client, h["editor"], script, ch)
        client.post(f"/lines/{line['id']}/approve", headers=h["editor"])
        # generate cover then publish v2 that no longer embeds the image; revoke
        # its license so its job is killed — only the export snapshot still
        # references the bytes.
        client.post(
            f"/characters/{ch['id']}/versions/{ch['current_version_id']}/cover-jobs",
            headers=h["editor"],
            json={"source_image_id": img["id"],
                  "crop": {"x": 0, "y": 0, "width": 0.9, "height": 0.9,
                           "target_width": 128, "target_height": 128, "force_fail": False}},
        )
        client.post("/cover-jobs/process", headers=h["admin"])
        client.post(f"/scripts/{script['id']}/exports", headers=h["editor"], json={"label": "e"})
        # orphan image (no version / job / export) should be deletable
        orphan = helpers.upload_image(client, h["editor"], name="orphan.png", color=(1, 2, 3))
        # The generated cover becomes historical once v2 is published and the
        # card switches to a new cover; but the export snapshot still cites it,
        # so its bytes must be retained.
        client.post(
            f"/characters/{ch['id']}/versions",
            headers=h["editor"],
            json={"appearance": "新造型", "tone": "新语气", "restrictions": "",
                  "change_note": "v2", "image_ids": []},
        )
        client.post(
            f"/characters/{ch['id']}/versions/{ch['current_version_id']}/cover-jobs",
            headers=h["editor"],
            json={"source_image_id": img["id"],
                  "crop": {"x": 0.1, "y": 0.1, "width": 0.7, "height": 0.7,
                           "target_width": 128, "target_height": 128, "force_fail": False}},
        )
        client.post("/cover-jobs/process", headers=h["admin"])
        report = client.post("/admin/cleanup?dry_run=false", headers=h["admin"]).json()
        deleted_image_ids = [d["id"] for d in report["deleted_images"]]
        deleted_asset_ids = [d["id"] for d in report["deleted_assets"]]
        protected_ids = [d["id"] for d in report["protected_by_exports"]]
        assert orphan["id"] in deleted_image_ids
        assert img["id"] not in deleted_image_ids  # still used by v1 + jobs
        # the v1 cover asset is historical (not active, superseded) yet export-protected
        exports = client.get("/exports", headers=h["viewer"]).json()
        exported_asset = exports[0]["asset_ids"][0]
        assert exported_asset in protected_ids
        assert exported_asset not in deleted_asset_ids
