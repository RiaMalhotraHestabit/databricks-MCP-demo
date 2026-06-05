from dotenv import load_dotenv
load_dotenv()

import os
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(
    host=os.getenv("DATABRICKS_HOST"),
    token=os.getenv("DATABRICKS_TOKEN")
)

for catalog in w.catalogs.list():
    print(catalog.name)