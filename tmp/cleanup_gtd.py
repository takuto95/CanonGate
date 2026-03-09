import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta

GTD_DIR = Path(r"c:\Users\takut\dev\Canon\.agent\gtd\private\next-actions")
ARCHIVE_DIR = Path(r"c:\Users\takut\dev\Canon\.agent\gtd\private\archive")

def cleanup():
    if not GTD_DIR.exists():
        print(f"GTD directory not found: {GTD_DIR}")
        return

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    
    # 3日以上前の auto_ ファイルをアーカイブ
    threshold = datetime.now() - timedelta(days=3)

    for f in GTD_DIR.glob("auto_*.md"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < threshold:
            dest = ARCHIVE_DIR / f.name
            try:
                shutil.move(str(f), str(dest))
                print(f"Archived: {f.name}")
                count += 1
            except Exception as e:
                print(f"Failed to move {f.name}: {e}")

    print(f"\nCleanup finished. Moved {count} files to archive.")

if __name__ == "__main__":
    cleanup()
