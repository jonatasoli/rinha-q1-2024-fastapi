# Rinha de Backend

## Tecnologias

- Python 3.12
- FastAPI 0.109.2
- Sqlalchemy 2.0
- Pydantic 2.6.1

## Como executar esse projeto?

Simplesmente executar `docker-compose up --build` e tudo vai ser executado.
Se for executar só o app sem o docker você pode fazer (com o poetry instalado):
`poetry install`
`poetry shell`
`task run`

### Observações

- O entrypoint está no docker-compose.yml o Dockerfile só tem o build
