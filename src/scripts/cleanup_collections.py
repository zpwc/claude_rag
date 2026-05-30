"""One-time script: delete stale collections before re-indexing."""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import chromadb
from src.core.config import VECTOR_STORE_DIR

client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
before = [c.name for c in client.list_collections()]
print('Collections before:', before)

for name in ['knowledge_base', 'kb_text', 'kb_code']:
    try:
        client.delete_collection(name)
        print(f'Deleted: {name}')
    except Exception as e:
        print(f'Skip {name}: {e}')

after = [c.name for c in client.list_collections()]
print('Collections after:', after)
