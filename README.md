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
| Embedding model | `bge-m3` |

Logok követése és leállítás:

```powershell
docker compose logs -f
docker compose down
```

A `docker compose down` megtartja az Ollama- és ChromaDB-adatokat. A `docker compose down -v` a tárolt modelleket és adatbázisadatokat is törli.

### Feldolgozási kimenetek

Időbélyeg nélkül a letöltés és feldolgozás mindig a normál `output/levelekN/`
könyvtárat használja. A `timestamp: true` opció egy teljes futást külön,
`output_<timestamp>/levelekN/` felépítésű archívumba ment. Így az archívumon
belüli oldalkönyvtárak neve változatlan marad, és a későbbi embedding mindig a
sima `output/` tartalmából dolgozhat.

## Konfiguráció

A beállításokat a `.env.example` alapján létrehozott, verziókezelésen kívüli `.env` fájlban lehet felülírni:

| Változó | Alapérték | Leírás |
| --- | --- | --- |
| `APP_PORT` | `8000` | Az API host portja |
| `OLLAMA_PORT` | `11434` | Az Ollama host portja |
| `CHROMA_EXPOSED_PORT` | `8001` | A ChromaDB host portja |
| `OLLAMA_EMBEDDING_MODEL` | `bge-m3` | A használt embedding modell |
| `EMBEDDING_BATCH_SIZE` | `32` | Egy Ollama-kérésben embeddingelt blokkok száma |
| `CHROMA_COLLECTION` | `customer_complaints` | A ChromaDB collection neve |
| `SOURCE_INSECURE` | `false` | `true` értéknél kikapcsolja a forrásoldal TLS-ellenőrzését |

Modellváltás után töltsd le az új modellt, majd indítsd újra a szolgáltatásokat:

```powershell
docker compose run --rm ollama-model-pull
docker compose up -d
```

## Embedding és keresés

A feldolgozott oldal blokkjainak embeddingelése mindig a sima `output/`
könyvtárból történik. Egy oldal embeddingelése:

```http
POST /api/v1/preprocessing/embeddings
Content-Type: application/json

{"page_id": 35}
```

Oldaltartományhoz `start_page` és `end_page` is megadható. A rendszer kizárólag
a nem üres `full_text` mezőket embeddingeli, stabil `levelekN:block_id`
azonosítókkal tölti őket ChromaDB-be, ezért az ismételt futtatás nem duplikál.

A szemantikus keresés fixen legfeljebb öt blokkot ad vissza:

```http
POST /api/v1/search
Content-Type: application/json

{"query": "hibás mosógép garanciális javítása"}
```

Minden találat tartalmazza a rangot, a `page_id` és `block_id` értéket, a teljes
`full_text` szöveget, a forrás URL-jét és a ChromaDB által adott távolságot.

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
