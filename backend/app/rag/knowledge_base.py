import os
import json
import time
from typing import Dict, Any, List, Optional

try:
    import faiss
    import numpy as np
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


class KnowledgeBase:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.index = None
        self.embeddings = {}
        self._load_knowledge()

    def _load_knowledge(self):
        knowledge_docs = [
            {
                "id": "IRPWM-4.2",
                "title": "Track Maintenance Block Requirements",
                "source": "IRPWM (Indian Railway Permanent Way Manual) - Prototype Reference",
                "content": "Minimum 120 minutes required for track maintenance blocks. Safety buffer of 15 minutes before and after block mandatory. Section must be formally handed over to Engineering department. All trains must be accounted for before block starts.",
                "category": "maintenance",
            },
            {
                "id": "GSR-7.3",
                "title": "Train Priority During Maintenance",
                "source": "G&SR (General & Subsidiary Rules) - Prototype Reference",
                "content": "Rajdhani and Shatabdi trains must not be delayed more than 10 minutes during planned maintenance blocks. Vande Bharat trains: maximum 12 minutes delay. Express trains: maximum 15 minutes. Passenger trains: maximum 20 minutes. Freight: maximum 30 minutes.",
                "category": "traffic",
            },
            {
                "id": "SWR-12.1",
                "title": "Section Handover Protocol",
                "source": "SWR (Station Working Rules) - Prototype Reference",
                "content": "Section must be formally handed over to maintenance team and verified clear before block starts. Station Master must confirm all trains have cleared the section. Block authority must be obtained from Controller.",
                "category": "operations",
            },
            {
                "id": "IRPWM-6.1",
                "title": "Safety Buffer Requirements",
                "source": "IRPWM - Prototype Reference",
                "content": "Mandatory 15-minute safety buffer before and after every maintenance block. No train movement allowed in the buffer zone without explicit permission from the Works Manager. Emergency access must be maintained at all times.",
                "category": "safety",
            },
            {
                "id": "GSR-9.2",
                "title": "Night Block Restrictions",
                "source": "G&SR - Prototype Reference",
                "content": "Night blocks (22:00-06:00) require additional authorization from Divisional Railway Manager. Minimum lighting requirements must be met. Additional safety personnel required.",
                "category": "safety",
            },
            {
                "id": "IRPWM-8.4",
                "title": "Resource Allocation for Track Maintenance",
                "source": "IRPWM - Prototype Reference",
                "content": "Track maintenance requires minimum 12 personnel (track gang), tamping machine, rail cutting equipment, and ballast regulator. For major repairs, crane and additional heavy equipment required.",
                "category": "resources",
            },
            {
                "id": "SOP-MAINT-01",
                "title": "Standard Maintenance Operating Procedure",
                "source": "Maintenance SOP - Prototype Reference",
                "content": "1. Engineer submits maintenance request with all details. 2. Planning system analyzes requirements. 3. AI generates candidate windows. 4. Optimization selects best window. 5. Simulation validates impact. 6. Officer reviews and approves/rejects. 7. If rejected, replanning with feedback. 8. Approved blocks are published.",
                "category": "procedure",
            },
            {
                "id": "HIST-BLOCK-001",
                "title": "Successful Track Maintenance Block - Shivajinagar",
                "source": "Historical Block Plans - Prototype Reference",
                "content": "Block HIST-2025-0142: Track maintenance on Shivajinagar-Khadki section. Window 09:30-11:30. 2 trains affected, 15 min total delay. Approved by Officer. Outcome: Successful completion within scheduled time.",
                "category": "historical",
            },
            {
                "id": "HIST-BLOCK-002",
                "title": "Rejected Maintenance Block - Pune-Lonavala",
                "source": "Historical Block Plans - Prototype Reference",
                "content": "Block HIST-2025-0203: Initial plan 22:00-01:00 rejected due to freight train conflict. Replanned to 01:30-03:30. 4 trains affected in V1, reduced to 1 in V2. Officer feedback: 'Avoid freight window, move to early morning'.",
                "category": "historical",
            },
            {
                "id": "HIST-BLOCK-003",
                "title": "Signal Maintenance Block - Hadapsar",
                "source": "Historical Block Plans - Prototype Reference",
                "content": "Block HIST-2025-0178: Signal maintenance at Hadapsar. Window 14:00-15:30. 1 train affected, 5 min delay. Adjacent signals manually controlled. Level crossing gates manned. Approved first time.",
                "category": "historical",
            },
            {
                "id": "RISK-MATRIX",
                "title": "Risk Assessment Matrix",
                "source": "Risk Framework - Prototype Reference",
                "content": "Risk scoring: 0-30 LOW, 30-60 MEDIUM, 60-100 HIGH. Safety risk weighted 30%, operational 25%, maintenance 20%, passenger 25%. HIGH risk requires additional justification. MEDIUM risk requires officer confirmation. LOW risk auto-approved with officer notification.",
                "category": "risk",
            },
            {
                "id": "CP-SAT-GUIDE",
                "title": "Optimization Constraints Reference",
                "source": "Optimization Guide - Prototype Reference",
                "content": "Hard constraints: maintenance duration, track availability, safety buffers, no train conflicts. Soft objectives: minimize delay, minimize affected trains, minimize passenger impact, maximize schedule feasibility. CP-SAT solver with 10-second time limit.",
                "category": "optimization",
            },
        ]

        self.documents = knowledge_docs

        if HAS_FAISS:
            self._build_index()

    def _build_index(self):
        try:
            dim = 128
            self.index = faiss.IndexFlatL2(dim)
            vectors = []
            for doc in self.documents:
                vec = self._simple_embed(doc["content"] + " " + doc["title"])
                vectors.append(vec)
            import numpy as np
            self.index.add(np.array(vectors, dtype=np.float32))
        except Exception:
            self.index = None

    def _simple_embed(self, text: str):
        import hashlib
        import numpy as np
        h = hashlib.md5(text.encode()).digest()
        seed = int.from_bytes(h[:4], 'big')
        rng = np.random.RandomState(seed)
        vec = rng.randn(128).astype(np.float32)
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        return vec

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        if self.index and HAS_FAISS:
            try:
                import numpy as np
                q_vec = self._simple_embed(query).reshape(1, -1)
                D, I = self.index.search(q_vec, min(k, len(self.documents)))
                results = []
                for idx in I[0]:
                    if 0 <= idx < len(self.documents):
                        doc = self.documents[idx].copy()
                        doc["score"] = 0.9
                        results.append(doc)
                return results
            except Exception:
                pass

        query_lower = query.lower()
        scored = []
        for doc in self.documents:
            score = 0
            text = (doc["content"] + " " + doc["title"]).lower()
            for word in query_lower.split():
                if word in text:
                    score += 1
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, doc in scored[:k]:
            r = doc.copy()
            r["score"] = min(0.95, 0.5 + score * 0.1)
            results.append(r)
        return results

    def get_all_documents(self) -> List[Dict[str, Any]]:
        return self.documents


knowledge_base = KnowledgeBase()
