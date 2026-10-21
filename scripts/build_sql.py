"""Write sql/02-settings.sql (keeps existing rows) and sql/02b-reset-settings.sql (overwrites)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import settings_data as s  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
(ROOT / "sql" / "02-settings.sql").write_text(s.to_sql(overwrite=False))
(ROOT / "sql" / "02b-reset-settings.sql").write_text(s.to_sql(overwrite=True))
print("wrote sql/02-settings.sql and sql/02b-reset-settings.sql,", len(s.SETTINGS), "settings")
