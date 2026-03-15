Pokopia local data workspace

This folder stores:
- sources.jsonl: source catalog with reliability notes
- schema.json: proposed entity schema for the searchable database
- *_seed.jsonl: small, attributed seed datasets (safe samples)
 - raw/: raw scraped JSONL from each source
 - processed/: normalized JSONL for app ingestion
 - images/: downloaded images (when available)

Seed coverage
- habitats_seed.jsonl contains only the "Featured Habitats" list from PokoHabitats.

Notes
- This is not an official database.
- Use sources.jsonl for attribution and later verification.
