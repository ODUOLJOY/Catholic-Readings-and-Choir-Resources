from sqlalchemy import create_engine
from sqlalchemy import inspect
from app.db.database import Base
import app.models.liturgical
import app.models.locations
import app.models.parish
import app.models.readings
import app.models.user
# Import other models if needed

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)

inspector = inspect(engine)
tables = set(inspector.get_table_names())
assert {"users", "dioceses", "deaneries", "parishes", "readings"} <= tables
