# ZK Rapport de présence

Read-only attendance reporting over a ZKBio Time 9 PostgreSQL database (PyQt6, French UI).
Project context and rules: `CLAUDE.md`.

## Windows setup

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Run

```bat
python -m zkreport
```

Settings are stored in `%APPDATA%\ZKReport\ZKReport\settings.db` (override with the
`ZKREPORT_SETTINGS` environment variable). The DB password, if any, is stored in the
Windows Credential Manager. Every DB session is read-only.

## Tests

```bat
pytest
```
