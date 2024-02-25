from datetime import datetime
import enum
from typing import List
from fastapi import FastAPI, status, HTTPException, Depends
from pydantic import parse_obj_as
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import joinedload
from src.models import Clients, Transactions
from sqlalchemy import QueuePool, select, desc, case, update
from sqlalchemy.ext.asyncio import create_async_engine


clients = {}


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
        db_transaction = Transactions(
            client_id=id,
            valor=transaction.valor,
            descricao=transaction.descricao,
            tipo=transaction.tipo,
        )
        client_db = await session.get(Clients, id, with_for_update=True)
        if not client_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Client not exist',
            )
        _new_balance = client_db.saldo - transaction.valor if transaction.tipo == 'd' else client_db.saldo + transaction.valor
        if transaction.tipo == 'd' and _new_balance < -client_db.limite:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='Client not found or concurrent update occurred',
            )
        client_db.saldo = _new_balance
        session.add(db_transaction)
        await session.commit()

    return TransactionResponse(limite=client_db.limite, saldo=client_db.saldo)


@main.get(
    '/clientes/{id}/extrato',
    status_code=status.HTTP_200_OK,
)
async def extract(id: int, db=Depends(get_async_session)):
    global clients
    async with db.begin() as session:
        if not clients:
            _clients = await session.scalars(select(Clients).with_for_update())
            for client in _clients.all():
                clients[client.id] = client

    async with db.begin() as session:
        db_transactions = await session.scalars(
            select(Transactions)
            .options(joinedload(Transactions.client, innerjoin=True))
            .where(Transactions.client_id == id)
            .order_by(desc(Transactions.id))
            .with_for_update(nowait=False)
            .limit(10)
        )
        _transactions = db_transactions.all()
    if not clients.get(id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Client not exist',
        )
    _balance = Balance(
        total=_transactions[0].client.saldo if _transactions else 0,
        limite=_transactions[0].client.limite if _transactions else clients.get(id).limite,
        data_extrato=datetime.now(),
    )
    transactions = parse_obj_as(List[LastTransaction], _transactions)
    return ExtractResponse(saldo=_balance, ultimas_transacoes=transactions)
