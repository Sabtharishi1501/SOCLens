"""
FastAPI application for SOCLens.

One real endpoint: POST /api/assess, which accepts an uploaded SOP file and
runs it through the full pipeline (extract -> build prompt -> call LLM,
Groq first then Gemini fallback -> validate + grounding-check the response).

Also serves the static frontend so the whole thing runs from one process:
`uvicorn main:app --reload` and open http://localhost:8000
"""

import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import extractor
import llm_client
import prompt_template
import validator
from config import HOST, PORT

app = FastAPI(title="SOCLens - AI SOC Maturity Assessment")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/assess")
async def assess(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the uploaded file: {e}")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        extraction = extractor.extract_text(file.filename, file_bytes)
    except extractor.ExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    prompt = prompt_template.build_prompt(
        extraction["text"], truncated=extraction["truncated"]
    )

    # Call the LLM and validate its response, retrying on EITHER failure
    # mode: both providers failing outright (LLMError), or a response that
    # parses but is malformed/incomplete (ValidationError). Raised to 3
    # attempts after observing multiple distinct failure modes stack up
    # within a single request.
    max_attempts = 3
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            llm_result = llm_client.get_llm_response(prompt)
        except llm_client.LLMError as e:
            print(f"[SOCLens] attempt {attempt}/{max_attempts} - both providers failed: {e}")
            if attempt == max_attempts:
                raise HTTPException(
                    status_code=502,
                    detail=f"The assessment could not be completed: {e}",
                )
            continue  # try the whole thing again rather than giving up early

        try:
            results = validator.parse_llm_response(
                llm_result["raw_text"], extraction["text"]
            )
            break  # success
        except validator.ValidationError as e:
            last_error = e
            print(
                f"[SOCLens] attempt {attempt}/{max_attempts} failed validation: {e}\n"
                f"[SOCLens] raw response was {len(llm_result['raw_text'])} chars: "
                f"{llm_result['raw_text'][:300]!r}"
            )
            if attempt == max_attempts:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"The AI's response could not be validated after "
                        f"{max_attempts} attempts: {e}"
                    ),
                )

    return {
        "filename": file.filename,
        "provider_used": llm_result["provider"],
        "truncated": extraction["truncated"],
        "original_chars": extraction["original_chars"],
        "used_chars": extraction["used_chars"],
        "results": results,
    }


_frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)