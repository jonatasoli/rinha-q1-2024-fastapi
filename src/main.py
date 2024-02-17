from datetime import datetime
from typing import List
from fastapi import APIRouter, FastAPI, status, HTTPException, Depends
from pydantic import parse_obj_as
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Clients, Transactions
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, select


main = APIRouter()


def create_app() -> FastAPI:
    """Factory function."""
    app = FastAPI()
    app.include_router(
        main,
        responses={status.HTTP_404_NOT_FOUND: {'description': 'Not found'}},
    )
    app.mount('/', main)
    return app

sqlalchemy_database_url = 'postgresql://rinha:rinha@localhost:5432/rinha'

engine = create_engine(
        sqlalchemy_database_url,
        pool_size=50,
        max_overflow=5,
)


def get_session() -> Session:
    with Session(bind=engine) as session:
        yield session



class Transaction(BaseModel):
    valor: int
    tipo: str
    descricao: str


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


@main.post('/clientes/{id}/transacoes', status_code=status.HTTP_200_OK)
def transaction(id: int, transaction: Transaction, db: Session = Depends(get_session)):
    db_client = db.scalar(select(Clients).where(Clients.id == id))
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Client not exist'
        )
    if transaction.tipo.lower() == 'c':
        db_client.saldo = db_client.saldo + transaction.valor
    elif transaction.tipo.lower() == 'd':
        _new_balance = db_client.saldo - transaction.valor
        if _new_balance < db_client.limite:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='transaction above limit!'
            )
        db_client.saldo = _new_balance
    else:
        raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='transaction type not permitted!'
        )
    db_transaction = Transactions(
        client_id = db_client.id,
        valor = transaction.valor,
        descricao=transaction.descricao,
        tipo=transaction.tipo.lower(),
    )
    db.add_all([db_transaction, db_client])
    db.commit()
        
    return TransactionResponse(limite=db_client.limite, saldo=db_client.saldo)


@main.get('/clientes/{id}/extrato', status_code=status.HTTP_200_OK)
def extract(id: int, db: Session = Depends(get_session)):
    db_client = db.scalar(select(Clients).where(Clients.id == id))
    if not db_client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='Client not exist'
        )
    _balance = Balance(
        total=db_client.saldo,
        limite=db_client.limite,
        data_extrato=datetime.now()
    )

    db_transactions = db.scalars(select(Transactions).where(Transactions.client_id==id)).all()
    transactions =  parse_obj_as(List[LastTransaction], db_transactions)
    return ExtractResponse(
        saldo=_balance,
        ultimas_transacoes=transactions
    )
