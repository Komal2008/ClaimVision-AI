def decide_claim(evidence_met, damage_visible):
    if not evidence_met:
        return ("not_enough_information", "Insufficient visual evidence")

    if damage_visible:
        return ("supported", "Damage visible in image")

    return ("contradicted", "Claimed damage not observed")
