# Qasa Finder

Scrapes rental apartment listings from [Qasa](https://qasa.com) in Stockholm and displays them in a filterable web UI.

## Scraper

Python script using Playwright to intercept GraphQL responses and extract apartment data (rent, size, rooms, address, link).

### Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

### Run

```bash
python scraper.py
```

Outputs `apartments.json` with all found listings.

## Frontend

SvelteKit + Tailwind CSS app that displays the scraped apartments in a responsive card grid with filtering and sorting.

### Setup

```bash
cd frontend
npm install
```

### Run

```bash
npm run dev
```

### Features

- Filter by max rent, min size, min rooms
- Sort by rent, size, or rooms (ascending/descending)
- Responsive layout (1/2/3 columns)
- Links to original Qasa listings
