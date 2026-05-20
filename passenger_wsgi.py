import sys
import os

# Add local path so that web_server is imported properly
sys.path.insert(0, os.path.dirname(__file__))

from web_server import app as application
