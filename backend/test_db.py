from app.database import engine

try:
    conn = engine.connect()
    print("SUCCESS")
    conn.close()
except Exception as e:
    print(e)