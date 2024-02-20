from datetime import datetime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy import ForeignKey
from sqlalchemy import String


class Base(DeclarativeBase):
    pass


class Clients(Base):
    __tablename__ = 'clients'

    id: Mapped[int] = mapped_column(primary_key=True)
    limite: Mapped[int] = mapped_column(default=0)
    saldo: Mapped[int] = mapped_column(default=0)
    criado_em: Mapped[datetime] = mapped_column(default=datetime.now())


class Transactions(Base):

    __tablename__ = 'transactions'

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey('clients.id'))
    valor: Mapped[int]
    descricao = mapped_column(String(10))
    tipo = mapped_column(String(1))
    realizado_em: Mapped[datetime] = mapped_column(default=datetime.now())
