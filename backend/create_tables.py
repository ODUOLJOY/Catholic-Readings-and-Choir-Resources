from app.db.database import Base, engine
import app.models.user
import app.models.parish
import app.models.parish_request
import app.models.readings
import app.models.payment
import app.models.saint
import app.models.choir
import app.models.download
import app.models.notification
import app.models.report
import app.models.favorite
import app.models.liturgical
import app.models.locations

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Tables created.")
