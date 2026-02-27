-- Scrape instance log: one row per scrape run
-- Tracks unique run id, config reference, run time, and listing count.
-- Run in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS scrape_instances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scrape_configuration_id INT8 NOT NULL REFERENCES scrape_configuration(id),
  ran_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  listings_count INT4 NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE scrape_instances IS 'One row per scraping run: id, config id, run time, and number of listings pulled';
COMMENT ON COLUMN scrape_instances.scrape_configuration_id IS 'ID of the scrape_configuration row that was used for this run';
COMMENT ON COLUMN scrape_instances.ran_at IS 'When the scrape was executed';
COMMENT ON COLUMN scrape_instances.listings_count IS 'Number of listings pulled in this run';

CREATE INDEX IF NOT EXISTS idx_scrape_instances_ran_at ON scrape_instances(ran_at DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_instances_config ON scrape_instances(scrape_configuration_id);
