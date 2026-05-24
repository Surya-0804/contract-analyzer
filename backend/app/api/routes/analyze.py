from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.llm import LLMProviderError, LLMResponseError
from app.nodes.contradict import contradict_node
from app.nodes.evaluate import evaluate_node
from app.nodes.ingestion import IngestionNode
from app.nodes.report import report_node
from app.nodes.segment import segment_node
from app.state import ContractState

router = APIRouter()
ingestion_node = IngestionNode()


@router.post("/analyze")
async def analyze_contract(file: UploadFile = File(...)):
    # Validate file type before reading the upload body into memory.
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_bytes = await file.read()

    try:
        raw_text, document_metadata = ingestion_node.ingest_with_metadata(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state: ContractState = {
        "file_bytes": file_bytes,
        "raw_pdf_text": raw_text,
        "document_metadata": document_metadata,
        "clauses": [],
        "contradictions": [],
        "final_report": "",
    }

    try:
        state = await segment_node(state)
        state = await evaluate_node(state)
        state = await contradict_node(state)
        state = await report_node(state)
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {
        "clauses": state["clauses"],
        "contradictions": state["contradictions"],
        "final_report": state["final_report"],
        "total": len(state["clauses"]),
    }
