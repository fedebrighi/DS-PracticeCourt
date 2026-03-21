from fastapi import FastAPI

app = FastAPI(title="Field Node")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "node": "field_node"}