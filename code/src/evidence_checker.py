def check_evidence(damage_visible, valid_image):
    if not valid_image:
        return (False, "Image not usable for review")

    if not damage_visible:
        return (False, "Claimed damage not visible")

    return (True, "Sufficient visual evidence")
