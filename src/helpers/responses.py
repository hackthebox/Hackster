import json


class SimpleResponse(object):
    """A simple response object."""

    def __init__(self, message: str, delete_after: int | None = None):
        self.message = message
        self.delete_after = delete_after

    def __str__(self):
        return json.dumps(dict(self), ensure_ascii=False)

    def __repr__(self):
        return self.__str__()
