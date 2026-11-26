# Action wiring helpers: convert string labels → {id, label} for module toolbar

def act(action_id: str, label: str):
    return {"id": action_id, "label": label}
