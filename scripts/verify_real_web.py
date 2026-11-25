"""Browser verification for the current organized real-data interface."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('verify_research_design.py')), run_name='__main__')
