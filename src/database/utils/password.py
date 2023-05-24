# flake8: noqa: ANN001

import bcrypt
from sqlalchemy import TypeDecorator
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.mutable import Mutable


class PasswordHash(Mutable):
    """
    Represents a bcrypt password hash.

    Attributes:
        hash (str): The hashed password value.
        rounds (int): The number of rounds used for hashing the password.
        desired_rounds (int): The desired number of rounds for hashing the password.

    Methods:
        __eq__(candidate): Hashes the candidate string and compares it to the stored hash.
        __repr__(): Returns a string representation of the object.
        __len__(): Returns the length of the hash.
        __getitem__(index): Returns the character at the specified index of the hash.
        __setitem__(index, value): Sets the character at the specified index of the hash to the given value.
        __delitem__(index): Removes the character at the specified index of the hash.
        insert(index, value): Inserts the given value at the specified index of the hash.
        coerce(key, value): Ensure that loaded values are PasswordHashes.
        new(password, rounds): Returns a new PasswordHash object for the given password and rounds.
    """

    def __init__(self, hash_, rounds=None):
        assert len(hash_) == 60, "bcrypt hash should be 60 chars."
        assert hash_.count("$") == 3, 'bcrypt hash should have 3x "$".'
        self.hash = str(hash_)
        self.rounds = int(self.hash.split("$")[2])
        self.desired_rounds = rounds or self.rounds

    def __eq__(self, candidate):
        """
        Hashes the candidate string and compares it to the stored hash.

        If the current and desired number of rounds differ, the password is
        re-hashed with the desired number of rounds and updated with the results.
        This will also mark the object as having changed (and thus need updating).
        """
        if isinstance(candidate, str):
            candidate = candidate.encode("utf8")
        if self.hash == bcrypt.hashpw(candidate, self.hash.encode("utf8")).decode("utf8"):
            if self.rounds < self.desired_rounds:
                self._rehash(candidate)
            return True
        return False

    def __repr__(self):
        """Simple object representation."""
        return f"<{type(self).__name__}>"

    def __len__(self):
        return len(self.hash)

    def __getitem__(self, index):
        return self.hash[index]

    def __setitem__(self, index, value):
        self.hash = self.hash[:index] + value + self.hash[index + 1 :]

    def __delitem__(self, index):
        self.hash = self.hash[:index] + self.hash[index + 1 :]

    def insert(self, index, value) -> None:
        """
        Insert the specified value into the hash at the given index.

        Args:
            index (int): The index where the value will be inserted.
            value (str): The value to be inserted into the hash.

        Returns:
            None
        """
        self.hash = self.hash[:index] + value + self.hash[index:]

    @classmethod
    def coerce(cls, key, value) -> "PasswordHash":
        """Ensure that loaded values are PasswordHashes."""
        if isinstance(value, PasswordHash):
            return value
        return super().coerce(key, value)

    @classmethod
    def new(cls, password, rounds) -> "PasswordHash":
        """Returns a new PasswordHash object for the given password and rounds."""
        if isinstance(password, str):
            password = password.encode("utf8")
        return cls(cls._new(password, rounds))

    @staticmethod
    def _new(password, rounds) -> str:
        """Returns a new bcrypt hash for the given password and rounds."""
        return bcrypt.hashpw(password, bcrypt.gensalt(rounds)).decode("utf8")

    def _rehash(self, password) -> None:
        """Recreates the internal hash and marks the object as changed."""
        self.hash = self._new(password, self.desired_rounds)
        self.rounds = self.desired_rounds
        self.changed()


class Password(TypeDecorator):
    """Allows storing and retrieving password hashes using PasswordHash."""

    impl = mysql.VARCHAR(60)

    def __init__(self, rounds=12, **kwds):
        self.rounds = rounds
        super().__init__(**kwds)

    def process_bind_param(self, value, dialect) -> str:
        """Ensure the value is a PasswordHash and then return its hash."""
        return self._convert(value).hash

    def process_result_value(self, value, dialect) -> PasswordHash:
        """Convert the hash to a PasswordHash, if it's non-NULL."""
        if value is not None:
            return PasswordHash(value, rounds=self.rounds)

    def validator(self, password) -> PasswordHash:
        """Provides a validator/converter for @validates usage."""
        return self._convert(password)

    def _convert(self, value) -> "PasswordHash":
        """
        Returns a PasswordHash from the given string.

        PasswordHash instances or None values will return unchanged.
        Strings will be hashed and the resulting PasswordHash returned.
        Any other input will result in a TypeError.
        """
        if isinstance(value, PasswordHash):
            return value
        elif isinstance(value, str):
            return PasswordHash.new(value, self.rounds)
        elif value is not None:
            raise TypeError(f"Cannot convert {value} to a PasswordHash")
