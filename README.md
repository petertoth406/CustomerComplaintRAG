# Futtatás

```powershell
python download.py --insecure
```

- `--range 35`: egy oldal
- `--range 34 36`: oldaltartomány
- `--output`: kimeneti gyökérmappa
- `--insecure`: TLS-ellenőrzés kikapcsolása
- `--save-blocks`: HTML-blokkok mentése

Példák:

```powershell
python download.py --range 35 --insecure
python download.py --range 34 36 --output "output" --insecure
python download.py --range 35 --save-blocks --insecure
```

Hibák: `output/errors.log`; hibás oldal után a feldolgozás folytatódik.



# TODO: Telepítő scriptet csinálni, később docker intéz mindent

BeautifoulSoup telepítése
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install beautifulsoup4
```
