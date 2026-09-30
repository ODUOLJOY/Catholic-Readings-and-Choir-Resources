import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from app.main import app
    from app.models.readings import Reading
    from app.routes.readings import router
    from app.db.database import get_db
    print("Backend imports successful!")
except Exception as e:
    print(f"Import error: {e}")
    sys.exit(1)
