import os

def get_user_path(base, user, subpath=""):
    return os.path.join(base, user, subpath)

def list_items(path):
    items = []
    for i in os.listdir(path):
        full = os.path.join(path, i)
        items.append({
            "name": i,
            "type": "folder" if os.path.isdir(full) else "file"
        })
    return items

def create_folder(path, name):
    os.makedirs(os.path.join(path, name), exist_ok=True)
