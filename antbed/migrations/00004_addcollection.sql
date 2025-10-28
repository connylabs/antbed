-- +goose Up
-- +goose StatementBegin

-- _Collection: Table to store the collection information of the collection
CREATE TABLE collection (
   id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   collection_name text NOT NULL,
   description text,
   info jsonb
);
CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON collection
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();

CREATE UNIQUE INDEX on collection (collection_name);

CREATE TABLE vfile_collection (
   id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
   vfile_id uuid REFERENCES vfile (id) NOT NULL,
   collection_id uuid REFERENCES collection (id) NOT NULL,
   info jsonb
);

CREATE INDEX on vfile_collection (collection_id);
CREATE INDEX on vfile_collection (vfile_id);
CREATE UNIQUE INDEX on vfile_collection (collection_id, vfile_id);

CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON vfile_collection
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();

-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP TABLE vfile_collection CASCADE;
DROP TABLE collection CASCADE;

-- +goose StatementEnd
