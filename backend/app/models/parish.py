from sqlalchemy import Column, Integer, String
from app.database import Base

class Parish(Base):
    __tablename__ = "parishes"

    id = Column(Integer, primary_key=True)

    name = Column(String)

    country = Column(String)