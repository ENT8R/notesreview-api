## Development
###### Using Ubuntu on Windows
`wt -p "Ubuntu"`

###### Activate virtual environment
`source venv/bin/activate`

###### Start the API
`sanic app.app`

## Scripts
###### `import.py`
import all notes from the latest notes dump (hosted on https://planet.openstreetmap.org/ or any other mirror):

`python import.py data/planet-notes-latest.osn`

---

###### `indices.py`
create all necessary indices for the database

`python indices.py`

---

###### `update.py`
updates the database by querying the OSM notes API in order to receive the latest notes since a given date of the last check

`python update.py`

---
