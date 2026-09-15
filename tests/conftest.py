import os
import sys

# Inject project root into sys.path to resolve module imports when testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
