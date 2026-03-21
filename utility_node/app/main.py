from fastapi import FastAPI

app = FastAPI(title="Utility Node")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "node": "utility_node"}