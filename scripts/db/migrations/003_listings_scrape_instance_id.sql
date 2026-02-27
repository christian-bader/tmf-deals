-- Add scrape_instance_id to listings so each row can reference the scrape run it came from.

ALTER TABLE listings
  ADD COLUMN IF NOT EXISTS scrape_instance_id UUID REFERENCES scrape_instances(id);

CREATE INDEX IF NOT EXISTS idx_listings_scrape_instance ON listings(scrape_instance_id);

COMMENT ON COLUMN listings.scrape_instance_id IS 'ID of the scrape_instances row for the run that pulled this listing';
