from app.database import engine
from app.database import Base

from app.models import *

Base.metadata.create_all(
    bind=engine
)

print("Tables created")