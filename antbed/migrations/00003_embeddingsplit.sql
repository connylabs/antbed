-- +goose Up
-- +goose StatementBegin

-- -- Prompt is
ALTER TABLE vector_vfile ADD COLUMN vsplit_id uuid REFERENCES vfile_split (id);

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
ALTER TABLE vector_vfile DROP COLUMN vsplit_id;
-- DROP TABLE map_vector CASCADE;

-- +goose StatementEnd
