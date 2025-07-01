import json
from typing import Any

class SimpleResponse(object):
    """A simple response object."""

    def __init__(self, message: str, delete_after: int | None = None, code: str | Any = None):
        self.message = message
        self.delete_after = delete_after
        self.code = code

    def __str__(self):
        return json.dumps(dict(self), ensure_ascii=False)  # type: ignore
 
    def __repr__(self):
        return self.__str__()
