# Streamlit Cloud entry point — delegates to the real app
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from streamlit_app.app import *  # noqa: F401,F403
