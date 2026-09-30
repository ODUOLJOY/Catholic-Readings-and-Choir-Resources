from sqlalchemy import create_engine
from app.db.database import Base
import app.models.liturgical
import app.models.readings
# Import other models if needed

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)

# Inspect tables
from sqlalchemy import inspect
inspector = inspect(engine)
print(inspector.get_table_names())
