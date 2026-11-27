import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import get_db
from app.main import app


def test_real_database_untouched(isolate_test_environment):
    env = isolate_test_environment
    # Verify current settings point to temp environment, not the real one
    assert Path(settings.DB_PATH).resolve() != env["real_db_path"]
    assert Path(settings.MEDIA_DIR).resolve() != env["real_media_dir"]
    assert Path(settings.DB_PATH).resolve() == Path(env["temp_db"]).resolve()
    assert Path(settings.MEDIA_DIR).resolve() == Path(env["temp_media"]).resolve()

    # Verify real DB file was not created or modified during test run
    if env["real_db_exists"]:
        assert env["real_db_path"].exists()
        assert env["real_db_path"].stat().st_mtime == env["real_db_mtime"]
        assert env["real_db_path"].stat().st_size == env["real_db_size"]
    else:
        assert not env["real_db_path"].exists()


def test_join_endpoint():
    with TestClient(app) as client:
        # Valid URLs: Google Meet, Zoom, Zoom subdomain, Teams, Teams live
        valid_urls = [
            "https://meet.google.com/abc-defg-hij",
            "https://zoom.us/j/123456789",
            "https://us02web.zoom.us/j/987654321",
            "https://teams.microsoft.com/l/meetup-join/19%3ameeting_xyz",
            "https://teams.live.com/meet/987654321",
        ]
        for url in valid_urls:
            res = client.post(
                "/api/v1/meetings/join",
                json={"meetingUrl": url, "language": "en", "slotName": "Morning Slot"},
            )
            assert res.status_code == 200, f"Expected 200 for {url}, got {res.status_code}: {res.text}"
            data = res.json()
            assert "meetingId" in data
            assert data["status"] == "scheduled"

        # Snake_case payload compatibility (meeting_url, slot_name)
        res_snake = client.post(
            "/api/v1/meetings/join",
            json={"meeting_url": "https://meet.google.com/xyz-uvwx-rst", "language": "en", "slot_name": "Slot A"},
        )
        assert res_snake.status_code == 200

        # Random URL gets 422
        res_random = client.post(
            "/api/v1/meetings/join",
            json={"meetingUrl": "https://example.com/not-a-meeting", "language": "en", "slotName": "Slot A"},
        )
        assert res_random.status_code == 422

        # HTTP (not HTTPS) gets 422
        res_http = client.post(
            "/api/v1/meetings/join",
            json={"meetingUrl": "http://meet.google.com/abc-defg-hij", "language": "en", "slotName": "Slot A"},
        )
        assert res_http.status_code == 422


def test_upload_endpoint(monkeypatch):
    with TestClient(app) as client:
        # 1. Valid small fake mp3 upload via multipart form fields (as frontend sends)
        fake_mp3 = b"ID3\x03\x00\x00\x00\x00\x00\x23fake_audio_stream_data_here"
        res = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("recording.mp3", fake_mp3, "audio/mpeg")},
            data={"language": "en", "slot_name": "Sprint Sync"},
        )
        assert res.status_code == 200, f"Upload failed: {res.text}"
        data = res.json()
        meeting_id = data["meetingId"]
        assert data["status"] == "scheduled"

        # Verify saved file at MEDIA_DIR/{id}/original.mp3
        saved_file = Path(settings.MEDIA_DIR) / meeting_id / "original.mp3"
        assert saved_file.is_file()
        assert saved_file.read_bytes() == fake_mp3

        # Verify DB row has media_type 'audio'
        with get_db() as conn:
            row = conn.execute("SELECT media_type, media_path FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            assert row["media_type"] == "audio"
            assert row["media_path"] == str(saved_file)

        # 2. .exe gets 422
        res_exe = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("installer.exe", b"MZexecutabledata", "application/x-msdownload")},
            data={"language": "en", "slot_name": "Sprint Sync"},
        )
        assert res_exe.status_code == 422

        # 3. File over MAX_UPLOAD_MB gets 413 and no partial file is left
        monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
        oversized = b"M" * (1024 * 1024 + 1024)  # > 1 MB
        res_large = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("heavy.mp4", oversized, "video/mp4")},
            data={"language": "en", "slot_name": "Large File Slot"},
        )
        assert res_large.status_code == 413

        # Check no partial file or directory left for heavy.mp4
        media_root = Path(settings.MEDIA_DIR)
        for child in media_root.iterdir():
            if child.is_dir():
                assert not (child / "original.mp4").exists()


def test_upload_then_media():
    with TestClient(app) as client:
        file_bytes = b"RIFFfake_wave_audio_data_content_12345"
        res_upload = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("sample.wav", file_bytes, "audio/wav")},
            data={"language": "en", "slot_name": "Test Slot"},
        )
        assert res_upload.status_code == 200
        meeting_id = res_upload.json()["meetingId"]

        # GET detail response and extract mediaUrl
        res_detail = client.get(f"/api/v1/meetings/{meeting_id}")
        assert res_detail.status_code == 200
        media_url = res_detail.json()["mediaUrl"]
        assert media_url == f"/api/v1/meetings/{meeting_id}/media"

        # GET mediaUrl and check bytes are equal
        res_media = client.get(media_url)
        assert res_media.status_code == 200
        assert res_media.content == file_bytes


def test_media_range():
    with TestClient(app) as client:
        sample_bytes = b"0123456789abcdefghijklmnopqrstuvwxyz"
        total_len = len(sample_bytes)  # 36
        res_upload = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("stream.mp4", sample_bytes, "video/mp4")},
            data={"language": "en", "slot_name": "Range Test"},
        )
        meeting_id = res_upload.json()["meetingId"]
        media_url = f"/api/v1/meetings/{meeting_id}/media"

        # Range request gets 206 with right bytes and Content-Range
        res_range = client.get(media_url, headers={"Range": "bytes=0-9"})
        assert res_range.status_code == 206
        assert res_range.content == sample_bytes[0:10]
        assert res_range.headers.get("content-range") == f"bytes 0-9/{total_len}"

        # Another slice: bytes 10-19
        res_range2 = client.get(media_url, headers={"Range": "bytes=10-19"})
        assert res_range2.status_code == 206
        assert res_range2.content == sample_bytes[10:20]
        assert res_range2.headers.get("content-range") == f"bytes 10-19/{total_len}"

        # Invalid range gets 416
        res_invalid_range = client.get(media_url, headers={"Range": "bytes=500-600"})
        assert res_invalid_range.status_code == 416

        # Unknown meeting gets 404
        res_unknown = client.get("/api/v1/meetings/00000000-0000-0000-0000-000000000000/media")
        assert res_unknown.status_code == 404

        # Meeting without a file gets 404 (joined meeting has no media file)
        res_join = client.post(
            "/api/v1/meetings/join",
            json={"meetingUrl": "https://meet.google.com/aaa-bbbb-ccc", "language": "en", "slotName": "No File"},
        )
        no_file_id = res_join.json()["meetingId"]
        res_no_media = client.get(f"/api/v1/meetings/{no_file_id}/media")
        assert res_no_media.status_code == 404


def test_list_endpoint():
    with TestClient(app) as client:
        # Create 3 meetings to test list ordering, limit, offset
        m_ids = []
        for i in range(3):
            r = client.post(
                "/api/v1/meetings/join",
                json={"meetingUrl": "https://meet.google.com/abc-defg-hij", "language": "en", "slotName": f"Meeting {i}"},
            )
            m_ids.append(r.json()["meetingId"])

        # 1. Plain array and newest first
        res_list = client.get("/api/v1/meetings")
        assert res_list.status_code == 200
        items = res_list.json()
        assert isinstance(items, list)
        assert len(items) >= 3
        # Newly joined meetings have createdAt and date derived
        assert items[0].get("createdAt") is not None
        assert items[0].get("date") is not None
        assert items[0].get("id") == items[0].get("meetingId")
        # Check timestamps sorted descending
        created_dates = [it.get("createdAt") for it in items if it.get("createdAt")]
        assert created_dates == sorted(created_dates, reverse=True)

        # Meeting with missing created_at has null createdAt and null date
        null_date_id = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO meetings (id, source, language, slot_name, status, created_at) VALUES (?, 'join', 'en', 'Null Date', 'pending', NULL)",
                (null_date_id,),
            )
        res_detail_null = client.get(f"/api/v1/meetings/{null_date_id}")
        assert res_detail_null.status_code == 200
        assert res_detail_null.json()["createdAt"] is None
        assert res_detail_null.json()["date"] is None

        # 2. Limit and offset
        res_paged = client.get("/api/v1/meetings?limit=2&offset=0")
        assert len(res_paged.json()) == 2
        res_offset = client.get("/api/v1/meetings?limit=2&offset=1")
        assert res_offset.json()[0]["meetingId"] == res_paged.json()[1]["meetingId"]

        # 3. q finds word in transcript segment (insert one segment by hand)
        target_id = m_ids[0]
        unique_word = "serendipity_unique_word"
        with get_db() as conn:
            conn.execute(
                "INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text) VALUES (?, 0, 5, 'Alice', ?)",
                (target_id, f"Let us discuss the {unique_word} concept."),
            )

        res_q = client.get(f"/api/v1/meetings?q={unique_word}")
        assert res_q.status_code == 200
        q_items = res_q.json()
        assert any(it["meetingId"] == target_id for it in q_items)

        # 4. q containing a quote character does not crash
        res_quote = client.get("/api/v1/meetings?q=quote'test\"double")
        assert res_quote.status_code == 200
        assert isinstance(res_quote.json(), list)

        # 5. No duplicate meetings even when multiple segments match
        with get_db() as conn:
            conn.execute(
                "INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text) VALUES (?, 6, 10, 'Bob', ?)",
                (target_id, f"Another segment with {unique_word}."),
            )
        res_dup_check = client.get(f"/api/v1/meetings?q={unique_word}")
        assert res_dup_check.status_code == 200
        matching_target = [it for it in res_dup_check.json() if it["meetingId"] == target_id]
        assert len(matching_target) == 1, "Meeting should appear exactly once (no duplicates)"


def test_detail_endpoint():
    with TestClient(app) as client:
        # Brand-new meeting returns empty lists and nulls, not an error
        res_join = client.post(
            "/api/v1/meetings/join",
            json={"meetingUrl": "https://meet.google.com/abc-defg-hij", "language": "en", "slotName": "Brand New"},
        )
        new_id = res_join.json()["meetingId"]

        res_detail = client.get(f"/api/v1/meetings/{new_id}")
        assert res_detail.status_code == 200
        data = res_detail.json()
        assert data["meetingId"] == new_id
        assert data["status"] == "scheduled"
        assert data["transcript"] == []
        assert data["speakers"] == []
        assert "topics" not in data
        assert data["actionItems"] == []
        assert "analytics" not in data
        assert data["summary"] is None
        assert data["mediaUrl"] is None
        assert data["mediaType"] is None
        assert data["processedSeconds"] is None
        assert data["durationSeconds"] is None
        assert data["error"] is None

        # Unknown id gets 404
        res_404 = client.get(f"/api/v1/meetings/{uuid.uuid4()}")
        assert res_404.status_code == 404


def test_patch_endpoint():
    with TestClient(app) as client:
        # Create meeting A and meeting B
        r_a = client.post(
            "/api/v1/meetings/join",
            json={"meetingUrl": "https://meet.google.com/abc-defg-hij", "language": "en", "slotName": "A"},
        )
        meet_a = r_a.json()["meetingId"]

        r_b = client.post(
            "/api/v1/meetings/join",
            json={"meetingUrl": "https://meet.google.com/abc-defg-hij", "language": "en", "slotName": "B"},
        )
        meet_b = r_b.json()["meetingId"]

        item_a = str(uuid.uuid4())
        item_b = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO action_items (id, meeting_id, text, owner, deadline, done) VALUES (?, ?, 'Task A', 'UserA', '2026-12-01', 0)",
                (item_a, meet_a),
            )
            conn.execute(
                "INSERT INTO action_items (id, meeting_id, text, owner, deadline, done) VALUES (?, ?, 'Task B', 'UserB', '2026-12-02', 0)",
                (item_b, meet_b),
            )

        # Toggle true
        res_patch1 = client.patch(f"/api/v1/meetings/{meet_a}/action-items/{item_a}", json={"done": True})
        assert res_patch1.status_code == 200
        assert res_patch1.json()["done"] is True
        assert res_patch1.json()["task"] == "Task A"
        assert res_patch1.json()["assignee"] == "UserA"
        assert res_patch1.json()["dueDate"] == "2026-12-01"

        # Verify persisted in database
        with get_db() as conn:
            row = conn.execute("SELECT done FROM action_items WHERE id = ?", (item_a,)).fetchone()
            assert row["done"] == 1

        # Toggle false
        res_patch2 = client.patch(f"/api/v1/meetings/{meet_a}/action-items/{item_a}", json={"done": False})
        assert res_patch2.status_code == 200
        assert res_patch2.json()["done"] is False

        with get_db() as conn:
            row = conn.execute("SELECT done FROM action_items WHERE id = ?", (item_a,)).fetchone()
            assert row["done"] == 0

        # 404 cases:
        # 1. Unknown meeting
        res_404_m = client.patch(f"/api/v1/meetings/{uuid.uuid4()}/action-items/{item_a}", json={"done": True})
        assert res_404_m.status_code == 404

        # 2. Unknown action item
        res_404_i = client.patch(f"/api/v1/meetings/{meet_a}/action-items/{uuid.uuid4()}", json={"done": True})
        assert res_404_i.status_code == 404

        # 3. Item of another meeting gets 404
        res_404_other = client.patch(f"/api/v1/meetings/{meet_a}/action-items/{item_b}", json={"done": True})
        assert res_404_other.status_code == 404


def test_status_mapping():
    with TestClient(app) as client:
        res = client.post(
            "/api/v1/meetings/join",
            json={"meetingUrl": "https://meet.google.com/abc-defg-hij", "language": "en", "slotName": "Status Test"},
        )
        meeting_id = res.json()["meetingId"]

        # In response, pending is mapped to scheduled
        assert res.json()["status"] == "scheduled"

        # In DB, stored status is still pending
        with get_db() as conn:
            row = conn.execute("SELECT status FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            assert row["status"] == "pending"

        # Detail endpoint also maps pending to scheduled
        res_detail = client.get(f"/api/v1/meetings/{meeting_id}")
        assert res_detail.json()["status"] == "scheduled"

        # When DB status is done -> mapped to completed
        with get_db() as conn:
            conn.execute("UPDATE meetings SET status = 'done' WHERE id = ?", (meeting_id,))
        res_done = client.get(f"/api/v1/meetings/{meeting_id}")
        assert res_done.json()["status"] == "completed"

        # When DB status is processing -> returned as processing
        with get_db() as conn:
            conn.execute("UPDATE meetings SET status = 'processing' WHERE id = ?", (meeting_id,))
        res_proc = client.get(f"/api/v1/meetings/{meeting_id}")
        assert res_proc.json()["status"] == "processing"

        # When DB status is failed -> returned as failed
        with get_db() as conn:
            conn.execute("UPDATE meetings SET status = 'failed' WHERE id = ?", (meeting_id,))
        res_failed = client.get(f"/api/v1/meetings/{meeting_id}")
        assert res_failed.json()["status"] == "failed"


def test_detail_media_type_and_status_fields():
    with TestClient(app) as client:
        # 1. Upload mp3 -> mediaType 'audio'
        fake_mp3 = b"ID3\x03\x00\x00\x00\x00\x00\x23fake_audio"
        res_mp3 = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("track.mp3", fake_mp3, "audio/mpeg")},
            data={"language": "en", "slot_name": "Audio Slot"},
        )
        assert res_mp3.status_code == 200
        mp3_id = res_mp3.json()["meetingId"]
        detail_mp3 = client.get(f"/api/v1/meetings/{mp3_id}").json()
        assert detail_mp3["mediaType"] == "audio"

        # 2. Upload mp4 -> mediaType 'video'
        fake_mp4 = b"\x00\x00\x00\x18ftypmp42fake_video"
        res_mp4 = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("clip.mp4", fake_mp4, "video/mp4")},
            data={"language": "en", "slot_name": "Video Slot"},
        )
        assert res_mp4.status_code == 200
        mp4_id = res_mp4.json()["meetingId"]
        detail_mp4 = client.get(f"/api/v1/meetings/{mp4_id}").json()
        assert detail_mp4["mediaType"] == "video"

        # 3. Join meeting (no media) -> mediaType null, processedSeconds null, durationSeconds null, error null
        res_join = client.post(
            "/api/v1/meetings/join",
            json={"meetingUrl": "https://meet.google.com/abc-test-fields", "language": "en", "slotName": "Join Slot"},
        )
        assert res_join.status_code == 200
        join_id = res_join.json()["meetingId"]
        detail_join = client.get(f"/api/v1/meetings/{join_id}").json()
        assert detail_join["mediaType"] is None
        assert detail_join["processedSeconds"] is None
        assert detail_join["durationSeconds"] is None
        assert detail_join["error"] is None

        # 4. Status 'failed' with error text 'test error' set by hand in test
        with get_db() as conn:
            conn.execute(
                "UPDATE meetings SET status = 'failed', error = 'test error' WHERE id = ?",
                (join_id,),
            )
        detail_failed = client.get(f"/api/v1/meetings/{join_id}").json()
        assert detail_failed["status"] == "failed"
        assert detail_failed["error"] == "test error"


def test_media_headers_and_playback():
    with TestClient(app) as client:
        # 1. Upload MP3
        fake_mp3 = b"ID3\x03\x00\x00\x00\x00\x00\x23fake_audio_bytes_content_123"
        res_mp3 = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("recording.mp3", fake_mp3, "audio/mpeg")},
            data={"language": "en", "slot_name": "MP3 Slot"},
        )
        assert res_mp3.status_code == 200
        mp3_id = res_mp3.json()["meetingId"]
        mp3_url = f"/api/v1/meetings/{mp3_id}/media"

        # Full request MP3
        r_mp3_full = client.get(mp3_url)
        assert r_mp3_full.status_code == 200
        assert r_mp3_full.headers.get("content-type") == "audio/mpeg"
        assert r_mp3_full.headers.get("accept-ranges") == "bytes"
        assert r_mp3_full.headers.get("content-disposition", "").startswith("inline")
        assert "attachment" not in r_mp3_full.headers.get("content-disposition", "")
        assert r_mp3_full.headers.get("content-length") == str(len(fake_mp3))

        # Range request MP3
        r_mp3_range = client.get(mp3_url, headers={"Range": "bytes=0-9"})
        assert r_mp3_range.status_code == 206
        assert r_mp3_range.headers.get("content-type") == "audio/mpeg"
        assert r_mp3_range.headers.get("accept-ranges") == "bytes"
        assert r_mp3_range.headers.get("content-disposition", "").startswith("inline")
        assert "attachment" not in r_mp3_range.headers.get("content-disposition", "")
        assert r_mp3_range.headers.get("content-length") == "10"
        assert r_mp3_range.headers.get("content-range") == f"bytes 0-9/{len(fake_mp3)}"

        # 2. Upload MP4
        fake_mp4 = b"\x00\x00\x00\x18ftypmp42video_sample_data_456789"
        res_mp4 = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("clip.mp4", fake_mp4, "video/mp4")},
            data={"language": "en", "slot_name": "MP4 Slot"},
        )
        assert res_mp4.status_code == 200
        mp4_id = res_mp4.json()["meetingId"]
        mp4_url = f"/api/v1/meetings/{mp4_id}/media"

        # Full request MP4
        r_mp4_full = client.get(mp4_url)
        assert r_mp4_full.status_code == 200
        assert r_mp4_full.headers.get("content-type") == "video/mp4"
        assert r_mp4_full.headers.get("accept-ranges") == "bytes"
        assert r_mp4_full.headers.get("content-disposition", "").startswith("inline")
        assert "attachment" not in r_mp4_full.headers.get("content-disposition", "")
        assert r_mp4_full.headers.get("content-length") == str(len(fake_mp4))

        # Range request MP4
        r_mp4_range = client.get(mp4_url, headers={"Range": "bytes=0-9"})
        assert r_mp4_range.status_code == 206
        assert r_mp4_range.headers.get("content-type") == "video/mp4"
        assert r_mp4_range.headers.get("accept-ranges") == "bytes"
        assert r_mp4_range.headers.get("content-disposition", "").startswith("inline")
        assert "attachment" not in r_mp4_range.headers.get("content-disposition", "")
        assert r_mp4_range.headers.get("content-length") == "10"
        assert r_mp4_range.headers.get("content-range") == f"bytes 0-9/{len(fake_mp4)}"

        # 3. 416 Invalid Range check for Accept-Ranges
        r_416 = client.get(mp4_url, headers={"Range": "bytes=5000-6000"})
        assert r_416.status_code == 416
        assert r_416.headers.get("accept-ranges") == "bytes"
        assert r_416.headers.get("content-range") == f"bytes */{len(fake_mp4)}"


def test_wal_concurrent_read_write(tmp_path):
    from app.db.database import SCHEMA_PATH, get_db_connection

    db_file = tmp_path / "test_wal_concurrent.db"
    conn1 = get_db_connection(str(db_file))
    conn2 = get_db_connection(str(db_file))
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn1.executescript(schema_sql)
        conn1.commit()

        # Connection 1 writes in a transaction without committing
        conn1.execute("BEGIN IMMEDIATE")
        conn1.execute(
            "INSERT INTO meetings (id, source, language, slot_name, status) VALUES ('wal-m1', 'join', 'en', 'Slot', 'pending')"
        )

        # Connection 2 reads simultaneously without blocking or failing with 'database is locked'
        rows = conn2.execute("SELECT COUNT(*) FROM meetings").fetchone()
        assert rows[0] == 0

        # Connection 1 commits
        conn1.commit()

        # Connection 2 now sees the written row
        rows_after = conn2.execute("SELECT COUNT(*) FROM meetings").fetchone()
        assert rows_after[0] == 1
    finally:
        conn1.close()
        conn2.close()


def test_media_outside_media_dir_returns_403():
    with TestClient(app) as client:
        outside_id = str(uuid.uuid4())
        media_root = Path(settings.MEDIA_DIR).resolve()
        outside_file = media_root.parent / f"outside_secret_{outside_id}.mp4"
        outside_file.write_bytes(b"secret_data")
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO meetings (id, source, language, slot_name, status, media_path) VALUES (?, 'upload', 'en', 'Slot', 'pending', ?)",
                    (outside_id, str(outside_file)),
                )
            res = client.get(f"/api/v1/meetings/{outside_id}/media")
            assert res.status_code == 403
            assert "Invalid media path" in res.json()["detail"]
        finally:
            if outside_file.exists():
                outside_file.unlink()


def test_upload_db_failure_cleans_up_media(monkeypatch):
    import sqlite3
    from contextlib import contextmanager

    with TestClient(app) as client:
        import app.services.meeting_service as ms

        real_get_db = ms.get_db

        @contextmanager
        def mock_get_db():
            with real_get_db() as real_conn:
                class FailConn:
                    def __getattr__(self, name):
                        return getattr(real_conn, name)

                    def execute(self, sql, *args, **kwargs):
                        if "INSERT INTO meetings" in str(sql):
                            raise sqlite3.OperationalError("Simulated DB failure")
                        return real_conn.execute(sql, *args, **kwargs)

                yield FailConn()

        monkeypatch.setattr(ms, "get_db", mock_get_db)

        fake_file = b"RIFFfake_audio_content_for_fail_test"
        res = client.post(
            "/api/v1/meetings/upload",
            files={"file": ("fail_test.wav", fake_file, "audio/wav")},
            data={"language": "en", "slot_name": "Fail Slot"},
        )
        assert res.status_code == 500

        # Verify no folder or file left in MEDIA_DIR for this failed upload
        media_root = Path(settings.MEDIA_DIR)
        for child in media_root.iterdir():
            if child.is_dir():
                original_wav = child / "original.wav"
                if original_wav.exists():
                    assert original_wav.read_bytes() != fake_file


def test_meeting_detail_contract_and_null_speaker():
    meeting_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO meetings (
                id, title, folder, slot_name, status, language, source, media_type,
                created_at, overview, project_progress, challenges, next_steps
            ) VALUES (?, 'Contract Meeting', 'General', 'Slot 1', 'done', 'en', 'upload', 'audio',
                      '2026-11-23T10:00:00Z', 'Overview text', '["Progress A"]', '["Challenge B"]', '["Next C"]')""",
            (meeting_id,),
        )
        conn.execute(
            """INSERT INTO speakers (meeting_id, name, color, talk_seconds, talk_percent, listen_percent)
               VALUES (?, 'Bob', '#5932ea', 120.0, 60.0, 40.0)""",
            (meeting_id,),
        )
        # 3 transcript rows: one with null speaker, one with Bob (in speakers), one with Alice (not in speakers)
        conn.execute(
            """INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text)
               VALUES (?, 0.0, 5.0, NULL, 'Hello world from unknown')""",
            (meeting_id,),
        )
        conn.execute(
            """INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text)
               VALUES (?, 5.0, 10.0, 'Bob', 'I will handle the deployment')""",
            (meeting_id,),
        )
        conn.execute(
            """INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text)
               VALUES (?, 10.0, 15.0, 'Alice', 'Sounds good to me')""",
            (meeting_id,),
        )
        conn.execute(
            """INSERT INTO action_items (id, meeting_id, text, owner, deadline, done)
               VALUES ('ai-1', ?, 'Handle deployment', 'Bob', 'tomorrow', 0)""",
            (meeting_id,),
        )

    with TestClient(app) as client:
        res = client.get(f"/api/v1/meetings/{meeting_id}")
        assert res.status_code == 200
        data = res.json()

        # 1. Top-level keys check
        expected_detail_keys = {
            "id", "meetingId", "title", "folder", "slotName", "status", "language",
            "meetingUrl", "createdAt", "date", "summary", "transcript", "speakers",
            "actionItems", "mediaUrl", "mediaType", "processedSeconds", "durationSeconds",
            "participantsCount", "error"
        }
        assert expected_detail_keys.issubset(data.keys())

        # 2. Transcript rows check
        assert len(data["transcript"]) == 3
        expected_transcript_keys = {
            "id", "timestampStart", "timestampEnd", "speakerName", "speakerColor", "text",
            "startTime", "endTime", "speaker"
        }
        for ut in data["transcript"]:
            assert set(ut.keys()) == expected_transcript_keys

        # Row 1: Null speaker -> defaults to "Speaker" and null color
        ut1 = data["transcript"][0]
        assert ut1["speakerName"] == "Speaker"
        assert ut1["speakerColor"] is None
        assert ut1["speaker"] == "Speaker"
        assert ut1["timestampStart"] == 0.0
        assert ut1["timestampEnd"] == 5.0
        assert ut1["startTime"] == 0.0
        assert ut1["endTime"] == 5.0

        # Row 2: Bob -> "Bob" and "#5932ea"
        ut2 = data["transcript"][1]
        assert ut2["speakerName"] == "Bob"
        assert ut2["speakerColor"] == "#5932ea"

        # Row 3: Alice -> "Alice" and null color (not in speakers table)
        ut3 = data["transcript"][2]
        assert ut3["speakerName"] == "Alice"
        assert ut3["speakerColor"] is None

        # 3. Speakers keys check
        assert len(data["speakers"]) == 1
        expected_speaker_keys = {
            "id", "name", "color", "role", "avatar", "talkDurationSeconds",
            "talkPercentage", "listenPercentage", "talkSeconds", "talkPercent",
            "listenPercent", "speakingTime"
        }
        assert set(data["speakers"][0].keys()) == expected_speaker_keys
        spk = data["speakers"][0]
        assert spk["talkDurationSeconds"] == 120.0
        assert spk["talkPercentage"] == 60.0
        assert spk["listenPercentage"] == 40.0

        # 4. Action items keys check
        assert len(data["actionItems"]) == 1
        expected_action_keys = {"id", "task", "description", "assignee", "dueDate", "done", "completed"}
        assert set(data["actionItems"][0].keys()) == expected_action_keys
        ai = data["actionItems"][0]
        assert ai["task"] == "Handle deployment"
        assert ai["assignee"] == "Bob"

        # 5. Summary keys check
        expected_summary_keys = {
            "overview", "projectProgress", "challenges", "challengesFaced", "actionItems", "nextSteps"
        }
        assert set(data["summary"].keys()) == expected_summary_keys


def test_list_endpoint_search_fts5():
    m1 = str(uuid.uuid4())
    m2 = str(uuid.uuid4())

    with get_db() as conn:
        conn.execute(
            "INSERT INTO meetings (id, title, overview, status) VALUES (?, 'Architecture Discussion', 'Overview A', 'done')",
            (m1,),
        )
        conn.execute(
            "INSERT INTO meetings (id, title, overview, status) VALUES (?, 'Marketing Sync', 'Overview B', 'done')",
            (m2,),
        )
        # m1 has two segments containing 'migration'
        conn.execute(
            "INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text) VALUES (?, 0.0, 5.0, 'Bob', 'Planning a database migration next week')",
            (m1,),
        )
        conn.execute(
            "INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text) VALUES (?, 5.0, 10.0, 'Carol', 'The migration script is ready')",
            (m1,),
        )
        # m2 has unrelated segments
        conn.execute(
            "INSERT INTO transcript_segments (meeting_id, start_time, end_time, speaker, text) VALUES (?, 0.0, 5.0, 'Dave', 'Discussing branding and banners')",
            (m2,),
        )

    with TestClient(app) as client:
        # 1. Whole word search finds the meeting
        res = client.get("/api/v1/meetings?q=migration")
        assert res.status_code == 200
        ids = [it["meetingId"] for it in res.json()]
        assert m1 in ids
        assert m2 not in ids

        # 2. Word prefix search (e.g. "migr" for "migration") finds it
        res_prefix = client.get("/api/v1/meetings?q=migr")
        assert res_prefix.status_code == 200
        ids_prefix = [it["meetingId"] for it in res_prefix.json()]
        assert m1 in ids_prefix
        assert m2 not in ids_prefix

        # 3. Query with quote character does not crash
        res_quote = client.get('/api/v1/meetings?q="migration"')
        assert res_quote.status_code == 200
        ids_quote = [it["meetingId"] for it in res_quote.json()]
        assert m1 in ids_quote

        res_malformed_quote = client.get('/api/v1/meetings?q="migr"ation')
        assert res_malformed_quote.status_code == 200

        # 4. Meeting with several matching rows appears exactly once
        res_count = client.get("/api/v1/meetings?q=migration")
        assert res_count.status_code == 200
        matching_m1 = [it for it in res_count.json() if it["meetingId"] == m1]
        assert len(matching_m1) == 1, "Meeting with multiple matching transcript segments must appear only once"




