-- +goose Up
-- +goose StatementBegin
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;



-- -- Openai_Vector: Table to store the vector information of the vector created by OpenAI
CREATE TABLE vector (
   id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   external_id text,
   external_provider text,
   vector_type text NOT NULL default 'default',
   subject_id text,
   subject_type text,
   info jsonb
);
CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON vector
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();

CREATE UNIQUE INDEX on vector (external_id, external_provider);
CREATE UNIQUE INDEX on vector (subject_id, subject_type, vector_type, external_provider);


-- Openai_File: Table to store the file information of the file created by OpenAI
CREATE TABLE vfile (
   id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   source_created_at TIMESTAMP,
   source_content_type text default 'text/plain',
   source text,
   source_filename text,
   subject_id text,
   subject_type text,
   info jsonb,
   pages text[],
   tokens int
);

CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON vfile
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();


CREATE UNIQUE INDEX on vfile (subject_id, subject_type);
CREATE INDEX on vfile (source);

-- -- -- Openai_Vector_File: Table to store the mapping between the vector and the file. many-many relationship
CREATE TABLE vector_vfile (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  vector_id uuid REFERENCES vector (id) NOT NULL,
  vfile_id uuid REFERENCES vfile (id) NOT NULL,
  external_id text,
  external_provider text,

  info jsonb
);

CREATE INDEX on vector_vfile (vector_id);
CREATE INDEX on vector_vfile (vfile_id);
CREATE UNIQUE INDEX on vector_vfile (vector_id, vfile_id);

CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON vector_vfile
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();


CREATE TABLE vfile_split (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  parts int,
  model text,
  vfile_id uuid REFERENCES vfile (id) NOT NULL,
  info jsonb,
  config_hash text,
  mode text,
  name text default 'default',
  chunk_size int default 1000,
  chunk_overlap int default 0
);

CREATE INDEX on vfile_split (vfile_id);
CREATE UNIQUE INDEX on vfile_split (config_hash, vfile_id);


CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON vfile_split
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();

-- -- -- Openai_Vector_File: Table to store the mapping between the vector and the file. many-many relationshi
CREATE TABLE embedding (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  char_start int,
  char_end int,
  model text,
  embedding_vector float[],
  status text default 'new',
  vfile_id uuid REFERENCES vfile (id) NOT NULL,
  info jsonb,
  content text,
  part_number int,
  vfile_split_id uuid REFERENCES vfile_split (id) NOT NULL
);

CREATE INDEX on embedding (vfile_id);


CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON embedding
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();



CREATE TABLE vfile_upload (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  vfile_id uuid REFERENCES vfile (id) NOT NULL,
  external_id text,
  external_provider text,
  filename text
);


CREATE INDEX on vfile_upload (vfile_id);
CREATE UNIQUE INDEX on vfile_upload (external_provider, vfile_id);


CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON vfile_upload
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();


-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP TABLE vector CASCADE;
DROP TABLE vfile CASCADE;
DROP TABLE vector_vfile CASCADE;
DROP FUNCTION trigger_set_timestamp;
DROP TABLE embedding;
DROP TABLE vfile_split;

-- DROP TABLE map_vector CASCADE;

-- +goose StatementEnd
