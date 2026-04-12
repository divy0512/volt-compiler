"""
VOLT Compiler — FastAPI Server
Run: uvicorn server:app --reload --port 5000
Then open volt-compiler.html in your browser
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from compiler import compile_volt
import uvicorn

app = FastAPI(title="VOLT Compiler API")

# Setup CORS (Allow the HTML frontend to call this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the data structure for the request body
class CompilationRequest(BaseModel):
    source: str

@app.post("/compile")
async def compile_route(request_data: CompilationRequest):
    try:
        # FastAPI automatically parses the JSON and validates it against CompilationRequest
        result = compile_volt(request_data.source)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "backend": "FastAPI", "version": "1.0"}

if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║     VOLT Compiler — Python Backend       ║")
    print("║     Running on http://localhost:5000     ║")
    print("╚══════════════════════════════════════════╝")
    uvicorn.run(app, host="0.0.0.0", port=5000)