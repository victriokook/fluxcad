import os
import sys

def prioritize_workspace(root):
    normalized = os.path.normcase(os.path.realpath(root))
    sys.path[:] = [root] + [p for p in sys.path if p and os.path.normcase(os.path.realpath(p)) != normalized]
