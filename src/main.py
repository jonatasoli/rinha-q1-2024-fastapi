from datetime import datetime
from functools import lru_cache
import enum
from typing import List
from fastapi import FastAPI, status, HTTPException, Depends
from pydantic import parse_obj_as
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.sql.elements import Cast
from src.models import Clients, Transactions
from sqlalchemy import QueuePool, select, desc, case, update
from sqlalchemy.ext.asyncio import create_async_engine


main = FastAPI()

sqlalchemy_database_url = (
    'postgresql+asyncpg://rinha:rinha@localhost:5432/rinha'
)

async_engine = create_async_engine(
    sqlalchemy_database_url, pool_size=45, max_overflow=40, poolclass=QueuePool
)


def get_async_session():
    return async_sessionmaker(async_engine, expire_on_commit=False)


class tipo_transacao(enum.StrEnum):
    c = 'c'
    d = 'd'


class Transaction(BaseModel):
    valor: int
    tipo: tipo_transacao
    descricao: str = Field(min_length=1, max_length=10)


class TransactionResponse(BaseModel):
    limite: int
    saldo: int


class Balance(BaseModel):
    total: int
    data_extrato: datetime
    limite: int


class LastTransaction(BaseModel):
    valor: int
    tipo: str
    descricao: str
    realizado_em: datetime
    model_config = ConfigDict(from_attributes=True)


class ExtractResponse(BaseModel):
    saldo: Balance
    ultimas_transacoes: list[LastTransaction]


@lru_cache
async def get_client_by_id(id, db):
    return await db.scalar(select(Clients.id).where(Clients.id == id))


@main.post(
    '/clientes/{id}/transacoes',
    status_code=status.HTTP_200_OK,
    response_model=TransactionResponse,
)
async def transaction(
    id: int,
    transaction: Transaction,
    db=Depends(get_async_session),
):
    async with db() as session:
        _client = await get_client_by_id(id, session)
        if not _client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Client not exist',
            )
        if transaction.tipo == 'd':
            query = (
                update(Clients)
                .where(Clients.id == id, Clients.saldo - transaction.valor < -Clients.limite)
                .values(saldo=Clients.saldo - transaction.valor)
                .returning(Clients.limite, Clients.saldo)
            )
        else:
            query = (
                update(Clients)
                .where(Clients.id == id)
                .values(saldo=Clients.saldo + transaction.valor)
                .returning(Clients.limite, Clients.saldo)
            )
        query_execution = await session.execute(query)
        _row = query_execution.fetchone()
        if not _row:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Client not found or concurrent update occurred',
            )
        db_transaction = Transactions(
            client_id=id,
            valor=transaction.valor,
            descricao=transaction.descricao,
            tipo=transaction.tipo,
        )
        session.add(db_transaction)
        await session.commit()

        return TransactionResponse(limite=_row[0], saldo=_row[1])


@main.get(
    '/clientes/{id}/extrato',
    status_code=status.HTTP_200_OK,
)
async def extract(id: int, db=Depends(get_async_session)):
    async with db.begin() as session:
        db_client = await session.get(Clients, id)
        if not db_client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Client not exist',
            )
        _balance = Balance(
            total=db_client.saldo,
            limite=db_client.limite,
            data_extrato=datetime.now(),
        )

        db_transactions = await session.scalars(
            select(Transactions)
            .where(Transactions.client_id == id)
            .order_by(desc(Transactions.id))
            .limit(10)
        )
    transactions = parse_obj_as(List[LastTransaction], db_transactions.all())
    return ExtractResponse(saldo=_balance, ultimas_transacoes=transactions)
