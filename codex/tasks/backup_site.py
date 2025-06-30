import shutil


def run(context: dict):
    print("[💾] Backing up site...")
    site_dir = context.get("site_dir", "public")
    backup_name = context.get("backup_name", "site_backup")
    shutil.make_archive(backup_name, 'zip', site_dir)
    print(f"[✅] Backup created at {backup_name}.zip")
