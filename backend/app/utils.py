import os
import re
import time
import json
import random
import hashlib
from collections import deque, defaultdict
from typing import Tuple

import requests

# -------- Basic input validation & sanitization --------
_ALLOWED_PATTERN = re.compile(r"^[A-Za-z0-9\s\-\&\'\(\)\,\.\+\/]+$")

def sanitize_item_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("itemName must be a string.")
    name = name.strip()
    if len(name) < 2 or len(name) > 120:
        raise ValueError("itemName length must be between 2 and 120 characters.")
    if not _ALLOWED_PATTERN.match(name):
        raise ValueError("itemName contains invalid characters.")
    # collapse excessive spaces
    name = re.sub(r"\s+", " ", name)
    return name

def truncate_words(s: str, limit: int = 30) -> str:
    words = s.strip().split()
    if len(words) <= limit:
        return s.strip()
    return " ".join(words[:limit])

# -------- Prompt engineering --------
SYSTEM_PROMPT = (
    "You are a concise menu copywriting assistant for restaurants. "
    "Always produce a short, vivid description and one upsell combo suggestion. "
    "The description must be at most 30 words."
)

USER_PROMPT_TEMPLATE = (
    "Task: Write a short, attractive menu description and a single upsell combo.\n"
    "Constraints: Description <= 30 words. Tone: appetizing, clear, not flowery.\n"
    "Input Item: \"{item_name}\"\n"
    "Output JSON with keys: description (string), upsell (string starting with 'Pair it with ')."
)

def build_prompt(item_name: str) -> Tuple[str, str]:
    """Returns (system_prompt, user_prompt)"""
    return SYSTEM_PROMPT, USER_PROMPT_TEMPLATE.format(item_name=item_name)

# -------- Mock LLM (deterministic + tasty) --------
_ADJECTIVES = [
    "smoky","creamy","zesty","aromatic","spiced","buttery","char-grilled","tangy",
    "hand-tossed","oven-fresh","herb-infused","buttermilk","velvety","caramelized","crisp","juicy"
]

_UPSELL_BY_KEYWORD = [
    (r"paneer|tikka", "Mango Lassi"),
    (r"pizza|margherita|pepperoni", "Garlic Bread"),
    (r"biryani", "Raita"),
    (r"burger|cheese", "Crispy Fries"),
    (r"noodle|ramen", "Spring Rolls"),
    (r"tandoori|kebab", "Mint Chutney"),
    (r"pasta", "Garlic Bread"),
    (r"salad", "Iced Tea"),
    (r"wrap|roll", "Masala Fries"),
]

def _deterministic_choice(seq, seed):
    rnd = random.Random(seed)
    return rnd.choice(seq)

def mock_generate(item_name: str, model_hint: str) -> Tuple[str, str]:
    """Generate description and upsell without calling an external LLM."""
    seed = int(hashlib.sha256(item_name.lower().encode()).hexdigest(), 16)
    adj1 = _deterministic_choice(_ADJECTIVES, seed)
    adj2 = _deterministic_choice(_ADJECTIVES, seed >> 1)
    base = f"{item_name}: {adj1}, {adj2} and crafted to highlight balanced spices and textures. Served hot for maximum flavor."
    description = truncate_words(base, 30)

    upsell = "Iced Tea"
    for pat, suggestion in _UPSELL_BY_KEYWORD:
        if re.search(pat, item_name, flags=re.I):
            upsell = suggestion
            break
    upsell_line = f"Pair it with a {upsell}!"
    return description, upsell_line

# -------- Optional OpenAI call (HTTP) --------
def call_openai(system_prompt: str, user_prompt: str, model_name: str) -> Tuple[str, str]:
    """
    Minimal HTTP call to OpenAI Chat Completions API.
    If OPENAI_API_KEY is not set, raises RuntimeError.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set; using mock mode instead.")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_name,  # e.g., "gpt-3.5-turbo" or "gpt-4o-mini"
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 120,
    }
    resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=20)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    # The model is instructed to output JSON with keys description, upsell.
    try:
        parsed = json.loads(content)
        description = truncate_words(str(parsed.get("description", "")).strip(), 30)
        upsell = str(parsed.get("upsell", "")).strip()
        if not upsell.lower().startswith("pair it with"):
            upsell = f"Pair it with {upsell}."
        return description, upsell
    except Exception:
        # If the LLM didn't return JSON, fall back to mock-style extraction
        # Simple heuristic: first line desc, second line upsell
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        description = truncate_words(lines[0], 30) if lines else "Tasty and satisfying."
        upsell = lines[1] if len(lines) > 1 else "Pair it with a refreshing beverage!"
        return description, upsell

# -------- Tiny rate limiter (per-IP leaky bucket) --------
WINDOW_SEC = 15 * 60
MAX_REQUESTS = 60  # e.g., 60 requests per 15 minutes

_BUCKETS = defaultdict(deque)  # ip -> deque[timestamps]

def check_rate_limit(ip: str) -> bool:
    now = time.time()
    dq = _BUCKETS[ip]
    # drop old timestamps
    while dq and now - dq[0] > WINDOW_SEC:
        dq.popleft()
    if len(dq) >= MAX_REQUESTS:
        return False
    dq.append(now)
    return True


def call_deepseek(system_prompt: str, user_prompt: str, model_name: str) -> Tuple[str, str]:
    """
    Call DeepSeek API (OpenAI-compatible) to generate description + upsell.
    """
    import os, json, requests
    api_key = os.getenv("DEEPSEEK_API_KEY")
    api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set; using mock mode instead.")

    url = f"{api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_name,  # e.g. "deepseek-chat" or "deepseek-coder"
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 120,
    }

    resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=20)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    # Expect JSON output (same as OpenAI path)
    try:
        parsed = json.loads(content)
        description = truncate_words(str(parsed.get("description", "")), 30)
        upsell = str(parsed.get("upsell", "")).strip()
        if not upsell.lower().startswith("pair it with"):
            upsell = f"Pair it with {upsell}."
        return description, upsell
    except Exception:
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        description = truncate_words(lines[0], 30) if lines else "Tasty and satisfying."
        upsell = lines[1] if len(lines) > 1 else "Pair it with a refreshing beverage!"
        return description, upsell


import os, re, json, requests
from typing import Tuple

# ... keep existing imports and helpers (sanitize_item_name, truncate_words, etc.)

_SERP_UPSELL_CANDIDATES = [
    # pattern, normalized upsell text (without "Pair it with")
    (r"lassi", "a Mango Lassi"),
    (r"garlic bread", "Garlic Bread"),
    (r"naan|butter naan", "Butter Naan"),
    (r"raita", "Raita"),
    (r"fries|chips", "Crispy Fries"),
    (r"salad", "a Fresh Salad"),
    (r"iced tea|lemon tea", "Iced Tea"),
    (r"soda|cola", "a Chilled Soda"),
    (r"mint chutney", "Mint Chutney"),
    (r"spring rolls", "Spring Rolls"),
    (r"gulab jamun", "Gulab Jamun"),
]

def serp_pick_upsell_from_text(text: str) -> str | None:
    text_low = text.lower()
    for pat, upsell in _SERP_UPSELL_CANDIDATES:
        if re.search(pat, text_low):
            return upsell
    return None

def call_serpapi_for_upsell(item_name: str) -> str:
    """
    Use SerpAPI (Google results) to infer a good upsell pairing for the dish.
    Returns a string like 'Pair it with Garlic Bread!' or a generic beverage if nothing matched.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return "Pair it with a refreshing beverage!"

    # A few phrasing variants to increase chance of good snippets
    queries = [
        f"best side to pair with {item_name}",
        f"{item_name} what to drink with",
        f"{item_name} accompaniment popular",
    ]

    try:
        found = None
        for q in queries:
            url = "https://serpapi.com/search.json"
            params = {"engine": "google", "q": q, "api_key": api_key, "hl": "en"}
            r = requests.get(url, params=params, timeout=20)
            if not r.ok:
                continue
            data = r.json()

            # scan organic results + snippets
            organic = data.get("organic_results", []) or []
            all_text = " ".join(
                filter(None, [*(res.get("title") for res in organic), *(res.get("snippet") for res in organic)])
            )
            # try known pairings
            found = serp_pick_upsell_from_text(all_text)
            if found:
                break

        if not found:
            # simple cuisine-specific fallbacks
            if re.search(r"paneer|tikka|tandoori|kebab|biryani|naan", item_name, flags=re.I):
                found = "a Mango Lassi"
            elif re.search(r"pizza|pasta", item_name, flags=re.I):
                found = "Garlic Bread"
            elif re.search(r"burger", item_name, flags=re.I):
                found = "Crispy Fries"
            else:
                found = "Iced Tea"

        return f"Pair it with {found}!"
    except Exception:
        return "Pair it with Iced Tea!"
