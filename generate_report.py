import requests
import os
from datetime import datetime, timedelta, timezone
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

repo_full = os.environ.get('GITHUB_REPOSITORY', '')
if repo_full:
    USERNAME = repo_full.split('/')[0]
else:
    USERNAME = 'Yien1024'
TOKEN = os.environ.get('GH_TOKEN')
if not TOKEN:
    raise RuntimeError('GH_TOKEN not set')
HEADERS = {'Authorization': f'Bearer {TOKEN}'}
