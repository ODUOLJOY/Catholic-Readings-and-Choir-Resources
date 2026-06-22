# test_connection.py

from sqlalchemy import create_engine

DATABASE_URL = "YOUR_DATABASE_URL"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("CONNECTED!")