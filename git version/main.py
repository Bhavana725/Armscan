from fastapi import FastAPI
from pydantic import BaseModel
import json, os
import numpy as np
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime

from upload_preprocess import process_uploaded_article
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()
PROCESSED_FOLDER = "processed_content"

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InputData(BaseModel):
    html: str
    url: str = None


# -----------------------------
# UTILS
# -----------------------------
def jaccard(a,b):
    return len(set(a)&set(b))/len(set(a)|set(b)) if a and b else 0

def minhash_similarity(a,b):
    return sum(1 for i,j in zip(a,b) if i==j)/len(a)

def simhash_distance(a,b):
    return bin(a^b).count("1")

def classify(conf, j3, semantic, preservation):
    if j3 > 0.85 and semantic > 0.85:
        return "Verbatim reuse"
    if semantic > 0.75 and preservation > 0.7:
        return "Light paraphrase"
    if semantic > 0.55:
        return "Moderate paraphrase"
    if semantic > 0.35:
        return "Heavy transformation"
    return "Independent content"


# -----------------------------
# MAIN API
# -----------------------------
@app.post("/analyze")
def analyze(data: InputData):

    # -------- STEP 1: HTML CLEANING (same as streamlit)
    soup = BeautifulSoup(data.html, "html.parser")

    for tag in soup(["script","style","noscript"]):
        tag.decompose()

    clean_text = soup.get_text(separator="\n")

    # -------- STEP 2: CREATE RAW JSON (same as your dataset)
    raw_json = {
        "id": data.url or "live_input",
        "url": data.url,
        "title": None,
        "category": None,
        "publication_date": None,
        "collected_at": datetime.utcnow().isoformat(),
        "raw_html": data.html,
        "clean_text": clean_text,
        "word_count": len(clean_text.split()),
        "char_count": len(clean_text),
        "language": "en"
    }

    json_buffer = StringIO(json.dumps(raw_json))

    # -------- STEP 3: PROCESS (same pipeline)
    uploaded = process_uploaded_article(json_buffer, "json")

    results = []

    # -------- STEP 4: COMPARE WITH CORPUS
    for file in os.listdir(PROCESSED_FOLDER):

        with open(os.path.join(PROCESSED_FOLDER, file)) as f:
            base = json.load(f)

        j3 = jaccard(uploaded["lexical"]["ngrams_3"],
                     base["lexical"]["ngrams_3"])

        j5 = jaccard(uploaded["lexical"]["ngrams_5"],
                     base["lexical"]["ngrams_5"])

        min_sim = minhash_similarity(
            uploaded["fingerprints"]["minhash_signature"],
            base["fingerprints"]["minhash_signature"]
        )

        sim_dist = simhash_distance(
            uploaded["fingerprints"]["simhash"],
            base["fingerprints"]["simhash"]
        )

        combined = uploaded["paragraphs"] + base["paragraphs"]
        vec = TfidfVectorizer(max_features=2000)
        tfidf = vec.fit_transform(combined)

        up = tfidf[:len(uploaded["paragraphs"])]
        bp = tfidf[len(uploaded["paragraphs"]):]

        matrix = cosine_similarity(up, bp)

        semantic = float(np.mean(np.max(matrix, axis=1)))

        preservation = float(
            np.sum(np.max(matrix,axis=1)>0.5)
            / len(uploaded["paragraphs"])
        )

        para_ratio = min(uploaded["structure"]["paragraph_count"],
                         base["structure"]["paragraph_count"]) / \
                     max(uploaded["structure"]["paragraph_count"],
                         base["structure"]["paragraph_count"])

        entity_ratio = jaccard(
            uploaded["entities"]["entity_set"],
            base["entities"]["entity_set"]
        )

        confidence = (
            0.2*j3 +
            0.2*semantic +
            0.15*para_ratio +
            0.15*entity_ratio +
            0.15*min_sim +
            0.15*(1 - sim_dist/64)
        )

        verdict = classify(confidence, j3, semantic, preservation)

        results.append({
            "id": base["id"],
            "confidence": round(confidence,3),
            "verdict": verdict
        })

    results = sorted(results, key=lambda x: x["confidence"], reverse=True)[:5]

    return {"top_matches": results,"processed": uploaded }
