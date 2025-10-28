-- +goose Up
-- +goose StatementBegin

-- -- Prompt is
CREATE TABLE prompt (
   id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   name text not NULL,
   prompt text,
   version text not NULL,
   latest boolean default false,
   variables text[],
   info jsonb,
   model text
);

CREATE UNIQUE INDEX on prompt (latest);
CREATE UNIQUE INDEX on prompt (version);

CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON prompt
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();

-- -- VFileSummary is
CREATE TABLE summary (
   id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
   vfile_id uuid REFERENCES vfile (id) NOT NULL,
   prompt_id uuid REFERENCES prompt (id),
   summary text,
   language text,
   title text,
   description text,
   tags text[],
   tokens int,
   info jsonb
);

CREATE TRIGGER set_timestamp_update
  BEFORE UPDATE ON summary
  FOR EACH ROW
  EXECUTE PROCEDURE trigger_set_timestamp();

CREATE UNIQUE INDEX on summary (vfile_id);
CREATE UNIQUE INDEX on summary (prompt_id);


-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP TABLE summary CASCADE;
DROP TABLE prompt CASCADE;

-- DROP TABLE map_vector CASCADE;

-- +goose StatementEnd
