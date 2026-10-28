CREATE TABLE IF NOT EXISTS class_categories(
    name TEXT PRIMARY KEY
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_class_categories_name_ci
ON class_categories(lower(name));

INSERT INTO class_categories(name) VALUES
    ('Strength'),
    ('Conditioning'),
    ('Hybrid'),
    ('Mobility'),
    ('Lower Body'),
    ('Upper Body'),
    ('Full Body')
ON CONFLICT DO NOTHING;
