from sqlalchemy import Column, Integer, String
from app.database import Base

class PendingReading(Base):
    __tablename__ = "pending_readings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    first_reading = Column(String)
    psalm = Column(String)
    gospel = Column(String)


class Reading(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    first_reading = Column(String)
    psalm = Column(String)
    gospel = Column(String)


class Saint(Base):
    __tablename__ = "saints"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    content = Column(String)


class ChoirSong(Base):
    __tablename__ = "choir_songs"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    lyrics = Column(String)


class DownloadItem(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    file_url = Column(String)