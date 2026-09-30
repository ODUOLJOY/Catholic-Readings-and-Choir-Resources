from app.core.config import Settings
import os

print(f"Current working directory: {os.getcwd()}")
print(f"Env file exists: {os.path.exists('.env')}")
with open('.env', 'r') as f:
    print(f"Env file content: {f.read()}")

try:
    s = Settings()
    print("Settings loaded successfully")
except Exception as e:
    print(f"Error loading settings: {e}")
