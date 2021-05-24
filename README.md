# notesreview-api
> API and backend for [notesreview](https://github.com/ENT8R/notesreview)

## Scripts
#### `import.py`
```sh
# Imports all notes from the latest notes dump
# (hosted on https://planet.openstreetmap.org/ or any other mirror)

# ${URL} needs to be replaced with the location of the notes dump
curl -o notes.osn.bz2 ${URL} && bzip2 -d notes.osn.bz2 && python db/scripts/import.py notes.osn
```

##### Structure
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

#### `indices.py`
```sh
# Creates all necessary indices for the database
python db/scripts/indices.py
```
---

#### `update.py`
```sh
# Updates the database by querying the OSM Notes API
# in order to receive the latest notes
# since a given date of the last check
python db/scripts/update.py
```
