import re
from typing import Any

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for SQLAlchemy declarative models, providing an automatic table name generation based on the class name.

    Attributes:
        id (Any): The primary key field for the table.
        __name__ (str): The name of the class used to generate the table name.
    """

    id: Any
    __name__: str

    # Generate __tablename__ automatically
    # noinspection PyMethodParameters
    @declared_attr
    def __tablename__(cls) -> str:  # noqa: N805
        """
        Generate a table name based on the class name by converting camel case to snake case.

        Returns:
            str: The generated table name in snake_case format.
        """
        return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()
