from app.database import Base

# Import ALL models here so SQLAlchemy can discover them
# before Base.metadata.create_all() is called.

from app.models.user import User
from app.models.parish import Parish
from app.models.readings import Reading

# Add these as you create them
try:
    from app.models.saint import Saint
except ImportError:
    Saint = None

try:
    from app.models.choir import ChoirResource
except ImportError:
    ChoirResource = None

try:
    from app.models.favorite import Favorite
except ImportError:
    Favorite = None

try:
    from app.models.download import Download
except ImportError:
    Download = None

try:
    from app.models.notification import Notification
except ImportError:
    Notification = None

try:
    from app.models.report import Report
except ImportError:
    Report = None

__all__ = [
    "Base",
    "User",
    "Parish",
    "Reading",
    "Saint",
    "ChoirResource",
    "Favorite",
    "Download",
    "Notification",
    "Report",
]