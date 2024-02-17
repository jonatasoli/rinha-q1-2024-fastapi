from datetime import datetime
from fastapi import APIRouter, FastAPI, status
from pydantic import BaseModel

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
    realizada_em: datetime


class ExtractResponse(BaseModel):
    saldo: Balance
    ultimas_transacoes: list[LastTransaction]


@main.post('/clientes/{id}/transacoes', status_code=status.HTTP_200_OK)
def transaction(id: int, transaction: Transaction) -> TransactionResponse:
    return TransactionResponse(limite=100000, saldo=-9098)


@main.get('/clientes/{id}/extrato', status_code=status.HTTP_200_OK)
def extract(id: int) -> ExtractResponse:
    return ExtractResponse(
        saldo=Balance(
            total=-9098,
            data_extrato=datetime.fromisoformat('2024-01-17T02:34:41.217753Z'),
            limite=100000,
        ),
        ultimas_transacoes=[
            LastTransaction(
                valor=10,
                tipo='c',
                descricao='descricao',
                realizada_em=datetime.fromisoformat(
                    '2024-01-17T02:34:38.543030Z'
                ),
            ),
            LastTransaction(
                valor=90000,
                tipo='d',
                descricao='descricao',
                realizada_em=datetime.fromisoformat(
                    '2024-01-17T02:34:38.543030Z'
                ),
            ),
        ],
    )
