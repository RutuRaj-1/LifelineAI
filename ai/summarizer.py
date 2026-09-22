"""Evidence-backed emergency brief.

Hard rules: the brief only restates what uploaded records say. It never diagnoses. Every item carries
source evidence (report id + snippet); items without evidence are dropped.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .rag import RagPipeline

DISCLAIMER = ("AI-generated summary of uploaded records only. It is not a diagnosis or medical advice. "
              "Verify against source documents; the treating doctor makes all decisions.")

CATEGORIES: dict[str, dict[str, Any]] = {
    "major_diseases": {
        "query": "past medical history known conditions chronic disease diabetes hypertension heart stroke asthma kidney",
        "label": r"(past medical|medical history|known conditions?|comorbidit\w*|chronic conditions?|history)",
        "cue": r"\b(diabet\w*|hypertension|asthma|copd|coronary|atrial fibrillation|ckd|kidney disease|epilep\w*|"
               r"stroke|tia|hypothyroid\w*|heart failure|cardiomyopathy|history of|h/o|k/c)\b",
    },
    "current_medicines": {
        "query": "current medications prescription tablets dose mg daily insulin",
        "label": r"(current )?(medications?|medicines?|drugs?|prescription|rx)",
        "cue": r"\b\d+(\.\d+)?\s?(mg|mcg|iu|units|ml)\b",
    },
    "allergies": {
        "query": "allergies allergic reaction anaphylaxis drug allergy",
        "label": r"(known )?allerg\w*",
        "cue": r"\b(allerg\w*|anaphyla\w*|hypersensitiv\w*|nkda)\b",
    },
    "previous_surgeries": {
        "query": "surgical history previous surgery operation procedure stent bypass",
        "label": r"(surgical|surgery|operative|procedures?)( history)?",
        "cue": r"\b(surg\w*|operat\w*|\w+ectomy|\w+plasty|stent\w*|bypass|cabg|fixation|implant\w*)\b",
    },
    "critical_risks": {
        "query": "risk flags anticoagulant bleeding pacemaker ejection fraction dialysis hypoglycemia immunosuppressed",
        "label": r"(risk flags?|critical (risks?|alerts?)|alerts?|precautions?)",
        "cue": r"\b(anticoag\w*|warfarin|apixaban|rivaroxaban|clopidogrel|bleeding|pacemaker|ejection fraction|"
               r"dialysis|hypoglyc\w*|immunosuppress\w*|pregnan\w*|seizure|difficult airway)\b",
    },
}
DIAGNOSIS_LANGUAGE = re.compile(
    r"\b(likely|probably|suspected|suggests?|consistent with|rule out|differential|you have|patient has)\b", re.I)
NEGATIVES = {"none", "nil", "n/a", "na", "-", "not applicable"}


def _evidence(chunk: dict) -> dict:
    return {"report_id": chunk["report_id"], "title": chunk["title"], "date": chunk.get("date"),
            "snippet": chunk["text"][:220].replace("\n", " "), "score": chunk.get("score")}


def _extract_items(cat: str, chunk: dict) -> list[str]:
    cfg, items = CATEGORIES[cat], []
    for raw in chunk["text"].splitlines():
        line = raw.strip(" -•*\t")
        if not line:
            continue
        label, _, value = line.partition(":")
        labelled = bool(value) and len(label) <= 40
        if labelled:
            other = [c for c in CATEGORIES if c != cat and re.fullmatch(CATEGORIES[c]["label"], label.strip(), re.I)]
            if other:
                continue  # line belongs to another category
            if re.fullmatch(cfg["label"], label.strip(), re.I):
                items += [p.strip() for p in re.split(r"[;,]", value) if p.strip()]
                continue
        if re.search(cfg["cue"], line, re.I):
            items.append(value.strip() if labelled and len(value) > 3 else line[:160])
    return [i[:160] for i in items if i.lower() not in NEGATIVES]


def extractive_brief(store, rag: RagPipeline, k: int = 8) -> dict:
    brief: dict[str, Any] = {}
    for cat, cfg in CATEGORIES.items():
        merged: dict[str, dict] = {}
        for chunk in rag.retrieve(store, cfg["query"], k):
            for item in _extract_items(cat, chunk):
                entry = merged.setdefault(item.lower(), {"text": item, "evidence": []})
                if all(e["report_id"] != chunk["report_id"] for e in entry["evidence"]):
                    entry["evidence"].append(_evidence(chunk))
        brief[cat] = list(merged.values())[:12]
    return brief


def _llm_brief(store, rag: RagPipeline, api_key: str, model: str) -> dict:
    from langchain_openai import ChatOpenAI

    chunks: dict[tuple, dict] = {}
    for cfg in CATEGORIES.values():
        for c in rag.retrieve(store, cfg["query"], 6):
            chunks[(c["report_id"], c["chunk"])] = c
    tagged = {f"S{i + 1}": c for i, c in enumerate(chunks.values())}
    context = "\n\n".join(f"[{t}] ({c['title']})\n{c['text']}" for t, c in tagged.items())
    system = ("You summarise a patient's uploaded medical records for an emergency team. Rules: use ONLY facts "
              "explicitly written in the sources; NEVER diagnose, infer, or suggest conditions or treatment; "
              "every item must cite source tags. Reply with JSON only: {\"major_diseases\":[{\"text\":str,"
              "\"sources\":[\"S1\"]}],\"current_medicines\":[...],\"allergies\":[...],\"previous_surgeries\":[...],"
              "\"critical_risks\":[...]}. Use empty lists when the sources say nothing.")
    llm = ChatOpenAI(model=model, api_key=api_key, temperature=0, timeout=30)
    raw = llm.invoke([("system", system), ("human", context)]).content
    data = json.loads(re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip())
    brief: dict[str, Any] = {}
    for cat in CATEGORIES:
        kept = []
        for it in data.get(cat, []):
            text, srcs = str(it.get("text", "")).strip(), [s for s in it.get("sources", []) if s in tagged]
            if not text or not srcs or DIAGNOSIS_LANGUAGE.search(text):
                continue
            words = {w for w in re.findall(r"[a-z]{4,}", text.lower())}  # grounding check
            if words and not any(words & set(re.findall(r"[a-z]{4,}", tagged[s]["text"].lower())) for s in srcs):
                continue
            kept.append({"text": text[:160], "evidence": [_evidence(tagged[s]) for s in srcs]})
        brief[cat] = kept
    return brief


def build_brief(docs: list[dict], rag: RagPipeline, reported: dict, *, api_key: str = "", model: str = "") -> dict:
    store = rag.build_index(docs)
    generated_by = "extractive-rag"
    brief: dict[str, Any] | None = None
    if api_key and docs:
        try:
            brief, generated_by = _llm_brief(store, rag, api_key, model), f"openai:{model}"
        except Exception:  # noqa: BLE001 - any LLM/network/JSON failure falls back to the deterministic path
            brief = None
    if brief is None:
        brief = extractive_brief(store, rag) if docs else {c: [] for c in CATEGORIES}
        generated_by = "extractive-rag"
    return {
        **brief,
        "reported_by_patient": reported,
        "sources": [{"report_id": d["id"], "title": d["title"], "date": d.get("date")} for d in docs],
        "insufficient_records": not docs or not any(brief[c] for c in CATEGORIES),
        "generated_by": generated_by,
        "embedder": rag.embedder.name,
        "disclaimer": DISCLAIMER,
    }
