import orjson


class Polygon(object):
    def __init__(self, polygon: str) -> None:
        polygon = orjson.loads(polygon)
        if 'type' not in polygon or 'coordinates' not in polygon:
            raise ValueError(
                'Polygon does not contain information about type or any coordinates'
            )

        self.type = polygon['type']
        self.coordinates = polygon['coordinates']
        self.check()

    def check(self) -> None:
        if self.type not in ['Polygon', 'MultiPolygon']:
            raise ValueError(
                'The GeoJSON shape must be either a Polygon or a MultiPolygon'
            )
        if type(self.coordinates) is not list:
            raise ValueError('Coordinates have to be supplied as an array')
