# Los Angeles County Parcel Scripts

Download parcel data from the LA County Assessor's public ArcGIS FeatureServer.

## Source

**LA County Parcels — Public ArcGIS FeatureServer**
`https://services3.arcgis.com/GVgbJbqm8hXASVYi/arcgis/rest/services/LA_County_Parcels/FeatureServer/0`

Max 2,000 records per query. Includes ownership, assessed values, use codes, and property characteristics.

## Data Availability

LA County's public endpoint has **thinner data** than San Diego's:
- Has: APN, address, use codes, assessed values, year built, bedrooms/baths, lat/lon
- Missing: Owner name and mailing address are NOT in the public FeatureServer (available through paid assessor roll products)

## Target ZIPs

90274, 90275, 90277, 90278, 90254, 90266, 90292, 90732, 90731

## Output

`data/boundaries/california/los-angeles/parcels/`
