-- +goose Up
-- +goose StatementBegin

-- -- Prompt is
ALTER TABLE vfile_collection ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL;
ALTER TABLE vfile_collection ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL;

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
alter table vfile_collection drop column created_at;
alter table vfile_collection drop column updated_at;
-- DROP TABLE map_vector CASCADE;

-- +goose StatementEnd
