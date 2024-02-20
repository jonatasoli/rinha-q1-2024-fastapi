from datetime import datetime
import enum
from typing import List
from fastapi import FastAPI, status, HTTPException, Depends
from pydantic import parse_obj_as
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.models import Clients, Transactions
from sqlalchemy import QueuePool, select, desc
from sqlalchemy.ext.asyncio import create_async_engine


main = FastAPI()

sqlalchemy_database_url = (
    'postgresql+asyncpg://rinha:rinha@localhost:5432/rinha'
)

async_engine = create_async_engine(
    sqlalchemy_database_url,
    pool_size=25,
    max_overflow=20,
    poolclass=QueuePool
)


def get_async_session():
    return async_sessionmaker(async_engine, expire_on_commit=False)


class tipo_transacao(enum.StrEnum):
    c='c'
    d='d'


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


@main.post(
    '/clientes/{id}/transacoes',
    status_code=status.HTTP_200_OK,
    response_model=TransactionResponse,
)
async def transaction(
    id: int,
    transaction: Transaction,
    db = Depends(get_async_session),
):
    async with db() as session:
        db_client = await session.get(Clients, id, with_for_update=True)
        if not db_client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Client not exist',
            )
        _new_balance = db_client.saldo + (
            -transaction.valor
            if transaction.tipo == 'd'
            else transaction.valor
        )
        if transaction.tipo == 'd' and _new_balance < -db_client.limite:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Transaction amount exceeds limit',
            )
        db_transaction = Transactions(
            client_id=db_client.id,
            valor=transaction.valor,
            descricao=transaction.descricao,
            tipo=transaction.tipo,
        )
        session.add(db_transaction)
        await session.flush()
        db_client.saldo=_new_balance
        await session.commit()

    return TransactionResponse(limite=db_client.limite, saldo=db_client.saldo)


@main.get(
    '/clientes/{id}/extrato',
    status_code=status.HTTP_200_OK,
)
async def extract(
    id: int, db = Depends(get_async_session)
):
    async with db.begin() as session:
        db_client = await session.get(Clients, id, with_for_update=True)
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
