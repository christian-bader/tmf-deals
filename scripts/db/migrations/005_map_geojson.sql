-- Store GeoJSON layers for the frontend map (e.g. SoCal ZCTA boundaries).
-- Run in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS map_geojson (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  geojson JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE map_geojson IS 'Named GeoJSON layers for the Search Configuration map; frontend fetches by name';
COMMENT ON COLUMN map_geojson.name IS 'Layer identifier, e.g. socal_zctas';
COMMENT ON COLUMN map_geojson.geojson IS 'GeoJSON FeatureCollection (type, features array)';

-- Allow anonymous read so the frontend can load the map
ALTER TABLE map_geojson ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read of map_geojson"
  ON map_geojson FOR SELECT
  TO anon
  USING (true);

-- Optional: allow service role to manage (for upload script)
CREATE POLICY "Allow service role full access to map_geojson"
  ON map_geojson FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
