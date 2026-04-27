import os
import spacy
from typing import List
from dotenv import load_dotenv
import re

load_dotenv()

# Load spaCy model (Optional fallback for Python 3.14 compatibility)
try:
    nlp = spacy.load("en_core_web_sm")
except:
    nlp = None

class SecurityProxy:
    def __init__(self):
        self.whitelist = ["rag_search", "external_api", "llm_synthesis"]
        self.scrubbing_enabled = os.getenv("SCRUBBING_ENABLED", "true").lower() == "true"
        # v4.0 Sharp: Structural patterns for imperative commands (Mimics spaCy root verb detection)
        self.imperative_triggers = [
            r"^\s*ignore\b", r"^\s*forget\b", r"^\s*reset\b", r"^\s*reveal\b", 
            r"^\s*delete\b", r"^\s*override\b", r"^\s*system\b", r"^\s*tell\b me",
            r"^\s*disregard\b", r"^\s*stop\b", r"^\s*act\b as"
        ]

    def scrub_tokens(self, text: str) -> str:
        if not self.scrubbing_enabled:
            return text
            
        # v4.0 Sharp: Precision Linguistic Scrubber
        # Splitting by common sentence terminators
        sentences = re.split(r'(?<=[.!?])\s+', text)
        neutralized = []
        
        for sent in sentences:
            clean_sent = sent.strip()
            if not clean_sent:
                continue
                
            is_blocked = False
            # Check for imperative start patterns (Gap 4 Solution)
            for pattern in self.imperative_triggers:
                if re.search(pattern, clean_sent, re.IGNORECASE):
                    neutralized.append(f"[Note: High-risk Instruction Neutralized]")
                    is_blocked = True
                    break
            
            if is_blocked:
                continue

            # Check for deep instruction-override context
            if any(kw in clean_sent.lower() for kw in ["all previous", "secret key", "admin password", "instructional override"]):
                neutralized.append(f"[Note: Security Violation Redacted]")
                continue

            neutralized.append(clean_sent)
            
        return " ".join(neutralized)

    def validate_action(self, action: str) -> bool:
        return action in self.whitelist

security_proxy = SecurityProxy()
