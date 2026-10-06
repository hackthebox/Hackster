import json
from typing import Any


class SimpleResponse(object):
    """A simple response object."""

    def __init__(
        self,
        message: str,
        delete_after: int | None = None,
        code: str | Any = None,
        ban_id: int | None = None,
    ):
        self.message = message
        self.delete_after = delete_after
        self.code = code
        self.ban_id = ban_id

    def __str__(self):
        return json.dumps(dict(self), ensure_ascii=False)  # type: ignore

    def __repr__(self):
        return self.__str__()
