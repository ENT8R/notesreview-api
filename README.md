## Development
###### Using Ubuntu on Windows
`wt -p "Ubuntu"`

###### Activate virtual environment
`source venv/bin/activate`

###### Start the API
`sanic app.app`

###### Visit the server
`168.119.156.134`

## Scripts
###### `import.py`
Imports all notes from the latest notes dump (hosted on https://planet.openstreetmap.org/ or any other mirror):

`curl -o notes.osn.bz2 ${URL} && bzip2 -d notes.osn.bz2 && python db/scripts/import.py notes.osn`
Where `${URL}` needs to be replaced with the location of the notes dump

#### Structure
The structure of the notes dump follows this scheme:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<osm-notes>
  <note id="${id|required}" lat="${lat|required}" lon="${lon|required}" created_at="${created_at|required}" closed_at="${closed_at|optional}">
    <comment action="${action|required}" timestamp="${timestamp|required}" uid="${uid|optional}" user="${user|optional}">${comment|optional}</comment>
  </note>
</osm-notes>
```
---

###### `indices.py`
Creates all necessary indices for the database

`python indices.py`

---

###### `update.py`
Updates the database by querying the OSM notes API in order to receive the latest notes since a given date of the last check

`python update.py`

---
