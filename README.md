# Futtatás

```powershell
python download.py --insecure
```

- `--range 35`: egy oldal
- `--range 34 36`: oldaltartomány
- `--output`: kimeneti gyökérmappa
- `--insecure`: TLS-ellenőrzés kikapcsolása

Példák:

```powershell
python download.py --range 35 --insecure
python download.py --range 34 36 --output "output" --insecure
```
