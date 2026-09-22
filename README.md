# Customer Complaint RAG

A projekt egy FastAPI-alapú alkalmazás fogyasztói panaszok letöltéséhez, feldolgozásához és későbbi szemantikus kereséséhez. A teljes helyi környezet az API mellett Ollamát, ChromaDB-t és egy ChromaDB-kezelőfelületet is tartalmaz.

## Telepítés és indítás Dockerrel

Előfeltételek:

- Docker Desktop (Windows alatt WSL 2 backenddel)
- Git

A projekt gyökerében futtasd:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Az első indítás tovább tarthat, mert a rendszer letölti az embedding modellt. Az API csak ennek sikeres befejezése után indul el.

### Elérhető felületek

| Szolgáltatás | URL |
| --- | --- |
| API | `http://localhost:8000` |
| Swagger | `http://localhost:8000/docs` |
| Ollama | `http://localhost:11434` |
| ChromaDB | `http://localhost:8001` |
| ChromaDB UI | `http://localhost:8090` |

A ChromaDB UI kapcsolati adatai:

| Beállítás | Érték |
| --- | --- |
| Chroma URL | `http://localhost:8001` |
| Tenant | `default_tenant` |
| Database | `default_database` |
| Ollama URL | `http://localhost:11434` |
| Embedding model | `qwen3-embedding:0.6b` |

Logok követése és leállítás:

```powershell
docker compose logs -f
docker compose down
```

A `docker compose down` megtartja az Ollama- és ChromaDB-adatokat. A `docker compose down -v` a tárolt modelleket és adatbázisadatokat is törli.

## Konfiguráció

A beállításokat a `.env.example` alapján létrehozott, verziókezelésen kívüli `.env` fájlban lehet felülírni:

| Változó | Alapérték | Leírás |
| --- | --- | --- |
| `APP_PORT` | `8000` | Az API host portja |
| `OLLAMA_PORT` | `11434` | Az Ollama host portja |
| `CHROMA_EXPOSED_PORT` | `8001` | A ChromaDB host portja |
| `OLLAMA_EMBEDDING_MODEL` | `qwen3-embedding:0.6b` | A használt embedding modell |
| `CHROMA_COLLECTION` | `customer_complaints` | A ChromaDB collection neve |
| `SOURCE_INSECURE` | `false` | `true` értéknél kikapcsolja a forrásoldal TLS-ellenőrzését |

Modellváltás után töltsd le az új modellt, majd indítsd újra a szolgáltatásokat:

```powershell
docker compose run --rm ollama-model-pull
docker compose up -d
```

## Lokális fejlesztői környezet

Python 3.12 vagy újabb verzióval, PowerShellben:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Az API ezután a `http://127.0.0.1:8000`, a Swagger pedig a `http://127.0.0.1:8000/docs` címen érhető el. Az Ollama és a ChromaDB lokális fejlesztéshez külön is elindítható Dockerrel:

```powershell
docker compose up -d ollama ollama-model-pull chromadb chromadb-ui
```

A tesztek futtatása:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

### VS Code

A repository tartalmazza a javasolt bővítményeket, a környezet-előkészítő és teszt taskokat, valamint a `FastAPI: debug` és `FastAPI: debug + auto-reload` indítási konfigurációkat. Nyisd meg a projekt gyökerét, futtasd a szükséges taskokat a `Terminal > Run Task...` menüből, majd indítsd a kiválasztott konfigurációt az `F5` billentyűvel.

## Opcionális NVIDIA GPU

Megfelelő NVIDIA driverrel és Docker GPU-támogatással az Ollama GPU-n is futtatható:

```powershell
docker compose -f compose.yaml -f compose.gpu.yaml up --build -d
```
