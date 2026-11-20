import uuid

from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app


def test_action_item_patch_and_mappers():
    with TestClient(app) as client:
        # 1. Join meeting returns mapped status
        join_res = client.post(
            "/api/v1/meetings/join",
            json={
                "meetingUrl": "https://meet.google.com/abc-defg-hij",
                "language": "en",
                "slotName": "default",
            },
        )
        assert join_res.status_code == 200
        join_data = join_res.json()
        assert join_data["status"] == "scheduled"
        meeting_id = join_data["meetingId"]

        # Stored value in DB is still 'pending'
        with get_db() as conn:
            db_row = conn.execute("SELECT status FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            assert db_row["status"] == "pending"

        # 2. Add action item for this meeting and another meeting
        other_meeting_id = str(uuid.uuid4())
        item_id_1 = str(uuid.uuid4())
        item_id_2 = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO meetings (id, source, language, slot_name, status) VALUES (?, 'join', 'en', 's', 'pending')",
                (other_meeting_id,),
            )
            conn.execute(
                "INSERT INTO action_items (id, meeting_id, text, owner, deadline, done) VALUES (?, ?, ?, ?, ?, ?)",
                (item_id_1, meeting_id, "Complete audit repair", "Alice", "2026-11-20", 0),
            )
            conn.execute(
                "INSERT INTO action_items (id, meeting_id, text, owner, deadline, done) VALUES (?, ?, ?, ?, ?, ?)",
                (item_id_2, other_meeting_id, "Other item", "Bob", "2026-11-21", 0),
            )

        # 3. PATCH 404 for missing meeting
        res_404_m = client.patch(
            f"/api/v1/meetings/nonexistent-meeting/action-items/{item_id_1}",
            json={"done": True},
        )
        assert res_404_m.status_code == 404

        # 4. PATCH 404 for missing item
        res_404_i = client.patch(
            f"/api/v1/meetings/{meeting_id}/action-items/nonexistent-item",
            json={"done": True},
        )
        assert res_404_i.status_code == 404

        # 5. PATCH 404 for item belonging to different meeting
        res_404_diff = client.patch(
            f"/api/v1/meetings/{meeting_id}/action-items/{item_id_2}",
            json={"done": True},
        )
        assert res_404_diff.status_code == 404

        # 6. Valid PATCH done=True
        patch_res = client.patch(
            f"/api/v1/meetings/{meeting_id}/action-items/{item_id_1}",
            json={"done": True},
        )
        assert patch_res.status_code == 200
        patch_data = patch_res.json()
        assert patch_data == {
            "id": item_id_1,
            "task": "Complete audit repair",
            "assignee": "Alice",
            "dueDate": "2026-11-20",
            "done": True,
        }

        # Verify DB column updated
        with get_db() as conn:
            item_row = conn.execute("SELECT done, text FROM action_items WHERE id = ?", (item_id_1,)).fetchone()
            assert item_row["done"] == 1
            assert item_row["text"] == "Complete audit repair"

        # Valid PATCH done=False
        patch_res2 = client.patch(
            f"/api/v1/meetings/{meeting_id}/action-items/{item_id_1}",
            json={"done": False},
        )
        assert patch_res2.status_code == 200
        assert patch_res2.json()["done"] is False
        with get_db() as conn:
            item_row = conn.execute("SELECT done FROM action_items WHERE id = ?", (item_id_1,)).fetchone()
            assert item_row["done"] == 0

        # 7. Detail response check: mapped status, empty lists, nulls (no invented values)
        detail_res = client.get(f"/api/v1/meetings/{meeting_id}")
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert detail_data["status"] == "scheduled"
        assert detail_data["transcript"] == []
        assert detail_data["speakers"] == []
        assert detail_data["topics"] == []
        assert detail_data["analytics"] is None
        assert len(detail_data["actionItems"]) == 1
        assert detail_data["actionItems"][0]["id"] == item_id_1
        assert detail_data["actionItems"][0]["task"] == "Complete audit repair"
        assert detail_data["actionItems"][0]["done"] is False

        # Status mapping: done -> completed
        with get_db() as conn:
            conn.execute("UPDATE meetings SET status = 'done' WHERE id = ?", (meeting_id,))
        detail_res_done = client.get(f"/api/v1/meetings/{meeting_id}")
        assert detail_res_done.json()["status"] == "completed"

        # Status mapping: processing -> processing
        with get_db() as conn:
            conn.execute("UPDATE meetings SET status = 'processing' WHERE id = ?", (meeting_id,))
        detail_res_proc = client.get(f"/api/v1/meetings/{meeting_id}")
        assert detail_res_proc.json()["status"] == "processing"

        # Status mapping: failed -> failed
        with get_db() as conn:
            conn.execute("UPDATE meetings SET status = 'failed' WHERE id = ?", (meeting_id,))
        detail_res_fail = client.get(f"/api/v1/meetings/{meeting_id}")
        assert detail_res_fail.json()["status"] == "failed"

        # 8. List endpoint mapping
        list_res = client.get("/api/v1/meetings")
        assert list_res.status_code == 200
        items = list_res.json()
        target_item = next(it for it in items if it["meetingId"] == meeting_id)
        assert target_item["status"] == "failed"

        # Cleanup
        with get_db() as conn:
            conn.execute("DELETE FROM meetings WHERE id IN (?, ?)", (meeting_id, other_meeting_id))
