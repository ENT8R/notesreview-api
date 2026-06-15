class BoundingBox(object):
    def __init__(self, input: str) -> None:
        bbox = [float(x) for x in input.split(',')]
        if len(bbox) != 4:
            raise ValueError(
                'The bounding box does not contain all required coordinates'
            )

        self.x1 = bbox[0]
        self.y1 = bbox[1]
        self.x2 = bbox[2]
        self.y2 = bbox[3]
        self.check()

    def check(self) -> None:
        if self.x1 > self.x2:
            raise ValueError(
                'The minimum longitude must be smaller than the maximum longitude'
            )
        if self.y1 > self.y2:
            raise ValueError(
                'The minimum latitude must be smaller than the maximum latitude'
            )
        if self.x1 < -180 or self.y1 < -90 or self.x2 > +180 or self.y2 > +90:
            raise ValueError(
                'The bounding box exceeds the size of the world, please specify a smaller bounding box'
            )
