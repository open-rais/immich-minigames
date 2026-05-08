from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)