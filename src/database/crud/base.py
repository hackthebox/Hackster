from typing import Any, Generic, Optional, Type, TypeVar, Sequence

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, Row, RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType", bound=BaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).
        Create, Update, and Delete are not implemented.

        **Parameters**

        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        """
        self.model = model

    async def read(self, db: AsyncSession, id_: int) -> Optional[ModelType]:
        return await db.get(self.model, id_)

    async def read_all(self, db: AsyncSession, order_by: str = None) -> Sequence[Row | RowMapping | Any]:
        query = select(self.model)
        if order_by:
            query = query.order_by(order_by)
        scalars = await db.scalars(query)
        return scalars.all()

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)  # type: ignore
        db.add(db_obj)
        await db.commit()
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: ModelType, obj_in: UpdateSchemaType) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            raise ValueError("Cannot update a model with a dict")
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        await db.commit()
        return db_obj

    async def delete(self, db: AsyncSession, *, id_: int) -> ModelType:
        obj = await db.get(self.model, id_)
        await db.delete(obj)
        await db.commit()
        return obj
