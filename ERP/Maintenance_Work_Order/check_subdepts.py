import os
from supabase import create_client
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(env_path)
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

import supabase._sync.client as supabase_client_mod
import re
original_match = re.match
supabase_client_mod.re.match = lambda *args, **kwargs: True
supabase = create_client(url, key)
supabase_client_mod.re.match = original_match

res = supabase.table("sub_departments").select("*").limit(1).execute()
print(f"Sub-Dept Columns: {res.data[0].keys() if res.data else 'No data'}")
