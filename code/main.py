import os
import pandas as pd
import time

from src.claim_extractor import extract_claim
from src.evidence_checker import check_evidence
from src.decision_engine import decide_claim
from src.pipeline import AnalysisPipeline

claims = pd.read_csv("../dataset/claims.csv")
history_df = pd.read_csv("../dataset/user_history.csv")

results = []

for _, row in claims.head(5).iterrows():
    
    history_row = history_df[
        history_df["user_id"] == row["user_id"]
    ]

    risk_flags = history_row.iloc[0]["history_flags"]

    claim_info = extract_claim(
        row["user_claim"]
    )

    image_path = row["image_paths"].split(";")[0]
    
    image_id = os.path.splitext(
         os.path.basename(image_path)
    )[0]

    full_path = "../dataset/" + image_path
    
    if not os.path.exists(full_path):
        continue
    
    pipeline = AnalysisPipeline()

    image_result = pipeline.run(
        full_path,
        row["claim_object"]
    )
    time.sleep(15)

    evidence_met, evidence_reason = check_evidence(
        image_result["damage_visible"],
        image_result["valid_image"]
    )

    claim_status, justification = decide_claim(
        evidence_met,
        image_result["damage_visible"]
    )

    results.append({
        "user_id": row["user_id"],
        "image_paths": row["image_paths"],
        
        "user_claim": row["user_claim"],
        "claim_object": row["claim_object"],

        "evidence_standard_met": evidence_met,
        "evidence_standard_met_reason": evidence_reason,

        "risk_flags": risk_flags,

        "issue_type": image_result["issue_type"],
        "object_part": image_result["object_part"],

        "claim_status": claim_status,
        "claim_status_justification": justification,

        "supporting_image_ids": image_id,

        "valid_image": image_result["valid_image"],

        "severity": image_result["severity"]
    })

output_df = pd.DataFrame(results)

output_df.to_csv(
    "output.csv",
    index=False
)

print("output.csv generated successfully")
print("Rows:", len(output_df)) 