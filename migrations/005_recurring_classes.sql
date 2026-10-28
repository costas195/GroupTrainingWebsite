CREATE TABLE IF NOT EXISTS class_series(
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
    starts_time TEXT NOT NULL,
    duration INTEGER NOT NULL,
    capacity INTEGER NOT NULL CHECK(capacity > 0),
    category TEXT NOT NULL,
    coach TEXT NOT NULL,
    description TEXT NOT NULL,
    warmup TEXT NOT NULL,
    main TEXT NOT NULL,
    finisher TEXT NOT NULL,
    starts_on TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS class_series_exceptions(
    series_id INTEGER NOT NULL REFERENCES class_series(id) ON DELETE CASCADE,
    occurrence_date TEXT NOT NULL,
    PRIMARY KEY(series_id, occurrence_date)
);

ALTER TABLE classes ADD COLUMN series_id INTEGER REFERENCES class_series(id);
ALTER TABLE classes ADD COLUMN occurrence_date TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_classes_series_occurrence
ON classes(series_id, occurrence_date);
