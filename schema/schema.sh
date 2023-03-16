jq -n 'reduce inputs as $s (.; .[input_filename|rtrimstr(".json")] += $s)' [!schema]*.json > schema.json
