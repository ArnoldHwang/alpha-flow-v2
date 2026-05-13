# src/research/build_state_expectancy_memory.py

import os
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from pymongo import MongoClient, UpdateOne

ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = ROOT / "results" / "research" / "transition_expectancy_all.csv"

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB_NAME = "alpha_flow_v2"
COLLECTION_NAME = "state_expectancy_memory"

HORIZONS = [1, 3, 5, 10, 20, 30, 60]


def load_env_file():
    env_path = ROOT / ".env"

    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_mongo():
    load_env_file()

    mongo_uri = os.getenv("MONGO_URI", DEFAULT_MONGO_URI)
    db_name = os.getenv("MONGO_DB_NAME", DEFAULT_DB_NAME)

    client = MongoClient(mongo_uri)
    db = client[db_name]

    return client, db


def safe_float(v, default=0.0):
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def safe_str(v, default="UNKNOWN"):
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass

    if v is None:
        return default

    s = str(v).strip()
    return s if s else default


def build_horizons(row):
    horizons = {}

    for h in HORIZONS:
        horizons[f"{h}d"] = {
            "horizon": f"{h}d",
            "winRate": safe_float(row.get(f"winRate_{h}d")),
            "avgReturn": safe_float(row.get(f"avgReturn_{h}d")),
            "medianReturn": safe_float(row.get(f"medianReturn_{h}d")),
            "expectancyGrade": safe_str(
                row.get(f"expectancyGrade_{h}d"), "UNKNOWN_EXPECTANCY"
            ),
        }

    return horizons


def build_doc(row):
    path_column = safe_str(row.get("pathColumn"), "UNKNOWN_PATH_COLUMN")
    path = safe_str(row.get("path"), "UNKNOWN_PATH")
    rows = int(safe_float(row.get("rows"), 0))

    memory_key = f"{path_column}|{path}"

    return {
        "memoryKey": memory_key,
        "sourceType": "transition_expectancy",
        "pathColumn": path_column,
        "path": path,
        "samples": rows,
        "horizons": build_horizons(row),
        "source": {
            "path": str(INPUT_PATH),
            "rows": None,
        },
        "updatedAt": now_iso(),
        "dataVersion": "state-expectancy-memory-v1",
    }


def ensure_indexes(collection):
    collection.create_index("memoryKey", unique=True)
    collection.create_index("sourceType")
    collection.create_index("pathColumn")
    collection.create_index("path")
    collection.create_index("samples")
    collection.create_index("updatedAt")


def main():
    print("=================================")
    print("🧠 BUILD STATE EXPECTANCY MEMORY")
    print("=================================")

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"missing file: {INPUT_PATH}")

    print(f"📄 input: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH, low_memory=False)

    print(f"rows: {len(df):,}")
    print(f"cols: {len(df.columns):,}")

    docs = []

    for _, row in df.iterrows():
        doc = build_doc(row)
        doc["source"]["rows"] = int(len(df))
        docs.append(doc)

    client, db = get_mongo()
    collection = db[COLLECTION_NAME]

    ensure_indexes(collection)

    ops = [
        UpdateOne(
            {"memoryKey": doc["memoryKey"]},
            {
                "$set": doc,
                "$setOnInsert": {"createdAt": now_iso()},
            },
            upsert=True,
        )
        for doc in docs
    ]

    result = collection.bulk_write(ops, ordered=False) if ops else None

    print(f"mongo db: {db.name}")
    print(f"collection: {COLLECTION_NAME}")
    print(f"docs: {len(docs):,}")

    if result:
        print(f"upserted: {result.upserted_count:,}")
        print(f"modified: {result.modified_count:,}")

    print("✅ done")

    client.close()


if __name__ == "__main__":
    main()
