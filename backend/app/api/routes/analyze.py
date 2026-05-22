from fastapi import APIRouter, UploadFile, File, HTTPException

from app.core.llm import LLMResponseError
from app.nodes.ingestion import IngestionNode
from app.nodes.segment import segment_node
from app.state import ContractState

router = APIRouter()
ingestion_node = IngestionNode()


@router.post("/analyze")
async def analyze_contract(file: UploadFile = File(...)):
	# ── Validate file type ──────────────────────────────
	if not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=400, detail="Only PDF files are accepted")

	file_bytes = await file.read()

	# ── Ingest ──────────────────────────────────────────
	try:
		raw_text, document_metadata = ingestion_node.ingest_with_metadata(file_bytes)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	# ── Build initial state ─────────────────────────────
	state: ContractState = {
		"file_bytes": file_bytes,
		"raw_pdf_text": raw_text,
		"document_metadata": document_metadata,
		"clauses": [],
		"contradictions": [],
		"final_report": "",
	}

	# ── Segment ─────────────────────────────────────────
	try:
		state = await segment_node(state)
	except LLMResponseError as e:
		raise HTTPException(status_code=502, detail=str(e))

	# ── Return clauses for now (graph wires the rest) ───
	return {"clauses": state["clauses"], "total": len(state["clauses"]) }
