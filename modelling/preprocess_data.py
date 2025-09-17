import os
import json
import pandas as pd


def main() -> None:
    csv_path = "video_clusters.csv"
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found at {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = {"pid", "dbscan_cluster_label"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in CSV: {sorted(missing)}")

    # Group by cluster and collect pids
    cluster_to_pids = (
        df.groupby("dbscan_cluster_label")["pid"]
        .apply(list)
        .to_dict()
    )

    # Normalize: keys as strings, values as list[int]
    normalized = {
        str(int(k)) if pd.notna(k) else "-1": [int(p) for p in v]
        for k, v in cluster_to_pids.items()
    }

    data_dir = os.path.join("data")
    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, "videos_by_cluster.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"Wrote {out_path} with {len(normalized)} clusters")


if __name__ == "__main__":
    main()


