from fastapi import APIRouter, UploadFile, File, HTTPException

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
		raw_text = ingestion_node.ingest(file_bytes)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))

	# ── Build initial state ─────────────────────────────
	state: ContractState = {
		"file_bytes": file_bytes,
		"raw_pdf_text": raw_text,
		"clauses": [],
		"contradictions": [],
		"final_report": "",
	}

	# ── Segment ─────────────────────────────────────────
	state = await segment_node(state)

	# ── Return clauses for now (graph wires the rest) ───
	return {"clauses": state["clauses"], "total": len(state["clauses"]) }
