"""Launcher — esegui da mvp/: python3 run_frontend.py"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import frontend.main  # noqa: F401  (side-effect: starts ui.run)
