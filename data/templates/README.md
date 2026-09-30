# Dataset templates (schema v2)

Five Tunisian templates, read-only starting points for `POST /api/v2/datasets {"template_key": ...}`.
They validate against `data/schema.v2.json` (generated from the Pydantic model) and have no
business-validation error. The v1 files `data/tunisia_*.json` are unchanged and still serve API v1.

## How they were built

1. **Migrated** from the v1 fixture with `app.domain.migrations_v1.migrate_v1_to_v2`.
2. **Enriched** (the compatibility-mode defaults were replaced):

| Kept from v1 | Changed / added |
|---|---|
| producer, crop name and type, buyers (ids, names, prices, max demand), distances, road condition, harvest total, main storage capacity and cost, vehicle count and capacity | ambient shelf life restored to the v1 `shelf_life_days`; harvest split into 2–3 lots over several days; a refrigerated facility added where relevant; per-trip transport costs instead of v1 per-kg-per-km costs; daily limits, delivery windows, contracts, minimum orders and later-season prices on some buyers; currency TND |

## Assumptions (to be replaced by field data)

| Topic | Value used | Why |
|---|---|---|
| Road factor | good 1.00, fair 1.15, poor 1.35 × distance | model default (road condition from v1) |
| Truck costs | 40–60 TND per trip + 1.1–1.4 TND per km (road-adjusted, both ways) | order of magnitude for 3–8 t trucks incl. fuel and driver |
| Refrigerated truck | 50 TND per trip + 1.3 TND per km | reefer premium |
| Driving time | 60 km/h, 12 h/day, 1–1.5 h loading per trip | one driver per truck |
| Dates long haul | 70 km/h, 16 h/day | Tozeur → Radès / Tunis (430–450 km) needs a relief driver to fit a round trip in one day |
| Cold storage | olives 1 500 kg @ 0.08, dates 3 000 kg @ 0.05, citrus 2 000 kg @ 0.07 TND/kg/day | small cold room next to the main store |
| Cold shelf life | olives 60 d, dates 365 d, citrus 60 d, tomatoes 14 d | refrigeration extends shelf life |
| Quality decay (price) | olives 0.3 %, dates 0.1 %, citrus 0.5 %, tomatoes 3 %, wheat 0 % per day | fresher produce sells higher |
| Storage loss | ambient: olives 0.2 %, dates 0.05 %, citrus 0.5 %, tomatoes 2 %, wheat 0.02 % per day; cold: lower | dehydration, rot, pests |
| Tomatoes | cold chain required (v1 `refrigerated_required`), only refrigerated storage and trucks | v1 data |

## Buyer constraints added

| Template | Buyer | Added |
|---|---|---|
| olives | Huilerie Sfax Export | max 1 500 kg/day (crushing capacity) |
| olives | Marche Central Tunis | max 800 kg/day |
| olives | Cooperative Export Sousse | contract minimum 1 000 kg |
| olives | EU Import Consortium | from day 7, minimum order 2 000 kg, 3.05 TND/kg from day 14 |
| dates | Exportateur Dattes Tozeur Bio | max 1 000 kg/day |
| dates | Conditionnement & Export Radès | minimum order 3 000 kg, 8.3 TND/kg from day 30 |
| dates | Grossiste Fruits Secs Sfax | max 1 500 kg/day |
| citrus | Groupement Interprofessionnel des Fruits (Export Marseille) | from day 5, minimum order 2 000 kg |
| citrus | Usine Jus & Nectar Cap Bon | contract minimum 2 000 kg |
| citrus | Marché Régional Nabeul | max 400 kg/day |
| tomatoes | Marché de Gros Bir El Kassâa | max 1 500 kg/day |
| tomatoes | Exportateur Primeurs Sahel | from day 2, max 800 kg/day |
| wheat | Office des Céréales - Silo Béja | contract minimum 5 000 kg |
| wheat | Minoterie des Grands Moulins Tunis | 1.55 TND/kg from day 20 |
