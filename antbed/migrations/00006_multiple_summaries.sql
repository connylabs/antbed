-- +goose Up
-- +goose StatementBegin

ALTER TABLE summary ADD COLUMN variant_name TEXT DEFAULT 'default' NOT NULL;

-- Drop the old unique index on vfile_id.
-- The actual name might vary. Check your DB or previous migration (00002_summary.sql).
-- 'summary_vfile_id_idx' is a common name if 'CREATE UNIQUE INDEX on summary (vfile_id)' was used.
DROP INDEX IF EXISTS summary_vfile_id_idx;
-- If it was a constraint like 'summary_vfile_id_key', use:
-- ALTER TABLE summary DROP CONSTRAINT IF EXISTS summary_vfile_id_key;

-- Drop the old unique index on prompt_id, as it's unlikely to be globally unique.
DROP INDEX IF EXISTS summary_prompt_id_idx;
-- ALTER TABLE summary DROP CONSTRAINT IF EXISTS summary_prompt_id_key;


CREATE UNIQUE INDEX summary_vfile_id_variant_name_idx ON summary (vfile_id, variant_name);

-- Re-add a non-unique index on prompt_id if it's still used for lookups and was dropped.
CREATE INDEX IF NOT EXISTS idx_summary_prompt_id ON summary (prompt_id);

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP INDEX IF EXISTS summary_vfile_id_variant_name_idx;
ALTER TABLE summary DROP COLUMN variant_name;

-- Recreate the old unique index on vfile_id
CREATE UNIQUE INDEX summary_vfile_id_idx ON summary (vfile_id);

-- Recreate the old unique index on prompt_id if it was indeed unique and needs to be restored.
-- This was likely an error in the original migration, so consider if it should be non-unique.
-- CREATE UNIQUE INDEX summary_prompt_id_idx ON summary (prompt_id);
-- Or, more likely, a non-unique one if it was dropped:
-- CREATE INDEX idx_summary_prompt_id ON summary (prompt_id);


-- +goose StatementEnd
