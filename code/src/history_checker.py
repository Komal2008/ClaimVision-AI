def get_history_flags(history_row):
    history_flags = str(history_row["history_flags"]).strip()

    if history_flags.lower() == "none":
        return ["none"]

    return [flag.strip() for flag in history_flags.split(";")]
