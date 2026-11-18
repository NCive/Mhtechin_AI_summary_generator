PRAGMA foreign_keys = ON;

-- 1. Meetings table
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT,
    folder TEXT,
    slot_name TEXT,
    language TEXT,
    source TEXT CHECK(source IN ('upload', 'join')),
    source_url TEXT,
    media_path TEXT,
    media_type TEXT CHECK(media_type IN ('video', 'audio')),
    status TEXT CHECK(status IN ('pending', 'processing', 'done', 'failed')) DEFAULT 'pending',
    error TEXT,
    duration_seconds REAL,
    processed_seconds REAL,
    created_at TEXT,
    overview TEXT,
    project_progress TEXT,
    challenges TEXT,
    next_steps TEXT
);

-- 2. Transcript segments table
CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    speaker TEXT,
    text TEXT NOT NULL
);

-- 3. Speakers table
CREATE TABLE IF NOT EXISTS speakers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT,
    talk_seconds REAL,
    talk_percent REAL,
    listen_percent REAL
);

-- 4. Action items table
CREATE TABLE IF NOT EXISTS action_items (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    owner TEXT,
    deadline TEXT,
    done INTEGER NOT NULL DEFAULT 0
);

-- 5. Windows table
CREATE TABLE IF NOT EXISTS windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    window_index INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    result_json TEXT
);

-- Foreign key indexes on meeting_id
CREATE INDEX IF NOT EXISTS idx_transcript_segments_meeting_id ON transcript_segments(meeting_id);
CREATE INDEX IF NOT EXISTS idx_speakers_meeting_id ON speakers(meeting_id);
CREATE INDEX IF NOT EXISTS idx_action_items_meeting_id ON action_items(meeting_id);
CREATE INDEX IF NOT EXISTS idx_windows_meeting_id ON windows(meeting_id);

-- FTS5 virtual table over transcript_segments.text
CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
    text,
    content='transcript_segments',
    content_rowid='id'
);

-- Triggers to keep transcript_fts in sync
CREATE TRIGGER IF NOT EXISTS transcript_segments_ai AFTER INSERT ON transcript_segments BEGIN
    INSERT INTO transcript_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS transcript_segments_ad AFTER DELETE ON transcript_segments BEGIN
    INSERT INTO transcript_fts(transcript_fts, rowid, text) VALUES('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS transcript_segments_au AFTER UPDATE ON transcript_segments BEGIN
    INSERT INTO transcript_fts(transcript_fts, rowid, text) VALUES('delete', old.id, old.text);
    INSERT INTO transcript_fts(rowid, text) VALUES (new.id, new.text);
END;
