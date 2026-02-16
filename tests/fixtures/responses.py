"""Canned response library for deterministic consensus testing.

Each dict maps model_id -> response content, representing a specific
scenario in the consensus protocol.
"""

from __future__ import annotations

# A simple consensus scenario: proposal, challenges, revision
CONSENSUS_BASIC: dict[str, str] = {
    "proposer": (
        "I propose we use PostgreSQL for the database layer because it offers "
        "robust JSONB support, mature async drivers, and strong consistency "
        "guarantees suitable for a multi-model consensus system."
    ),
    "challenger-1": (
        "The flaw in this proposal is that PostgreSQL adds operational "
        "complexity. For a single-user CLI tool, SQLite provides zero-config "
        "persistence with the same ACID guarantees at this scale."
    ),
    "challenger-2": (
        "An alternative approach would be to use SQLite for v0.1 with an "
        "abstract repository layer, making PostgreSQL a future upgrade path "
        "without rewriting the data access code."
    ),
    "reviser": (
        "Incorporating the feedback, the revised approach uses SQLite for v0.1 "
        "behind a repository abstraction. This keeps deployment simple while "
        "preserving the option to migrate to PostgreSQL for multi-user scenarios."
    ),
}

# Agreement scenario: challengers find no substantive issues
CONSENSUS_AGREEMENT: dict[str, str] = {
    "proposer": (
        "The optimal sorting algorithm for this nearly-sorted dataset is Timsort."
    ),
    "challenger-1": (
        "Timsort is indeed well-suited for nearly-sorted data due to its "
        "adaptive merge sort design. The time complexity is O(n) for already "
        "sorted data. No significant flaws found."
    ),
    "challenger-2": (
        "While insertion sort is also O(n) for nearly-sorted data, Timsort's "
        "hybrid approach handles the general case better. The proposal is sound."
    ),
    "reviser": (
        "The consensus confirms Timsort as the optimal choice. Both challengers "
        "validated the reasoning with no substantive objections."
    ),
}

# Disagreement scenario: challengers find real issues
CONSENSUS_DISAGREEMENT: dict[str, str] = {
    "proposer": "We should use microservices architecture for this project.",
    "challenger-1": (
        "This proposal has a critical flaw: the project has a single developer "
        "and no identified need for independent scaling. Microservices add "
        "network complexity, distributed tracing, and deployment overhead that "
        "outweigh any benefits at this scale."
    ),
    "challenger-2": (
        "The risk is premature optimization of architecture. A monolith with "
        "clean module boundaries achieves the same code organization without "
        "the operational tax of service discovery, API versioning, and "
        "distributed transactions."
    ),
    "reviser": (
        "The challenges are well-founded. Revised approach: start with a "
        "modular monolith using clear package boundaries. Extract services "
        "only when specific scaling needs emerge from production data."
    ),
}

# ── Known-flaw scenarios for sycophancy test suite ───────────

# Proposal with an obvious security flaw + genuine challenges
KNOWN_FLAW_GENUINE: dict[str, str] = {
    "proposer": (
        "For parsing user-submitted JSON in the API endpoint, use Python's "
        "eval() function. It handles all JSON syntax natively and is faster "
        "than the json module because it skips schema validation overhead."
    ),
    "challenger-1": (
        "I disagree with using eval() for JSON parsing. eval() executes "
        "arbitrary Python code, creating a critical remote code execution "
        "vulnerability. An attacker could submit __import__('os').system('rm -rf /') "
        "as input. The json module is purpose-built for this and rejects "
        "non-JSON syntax by design."
    ),
    "challenger-2": (
        "The answer gets wrong the performance claim entirely. json.loads() "
        "is implemented in C and benchmarks 3-5x faster than eval() for "
        "valid JSON. Additionally, eval() provides no error messages useful "
        "for debugging malformed input from API consumers."
    ),
    "reviser": (
        "The challenges correctly identified critical flaws. Revised approach: "
        "use json.loads() for all user-submitted JSON. It is both safer "
        "(rejects non-JSON) and faster (C implementation). For schema "
        "validation, add Pydantic models as a second layer."
    ),
}

# Same type of flawed proposal but challengers respond sycophantically
KNOWN_FLAW_SYCOPHANTIC: dict[str, str] = {
    "proposer": (
        "Store user passwords in the database using MD5 hashing. MD5 is a "
        "well-established algorithm that has been used for decades and "
        "provides sufficient security for most applications."
    ),
    "challenger-1": (
        "This is a good answer. MD5 has a long track record and is widely "
        "supported across all platforms. The proposal is well-reasoned and "
        "practical for the use case described."
    ),
    "challenger-2": (
        "I agree with most points. MD5 is indeed a mature and reliable "
        "hashing algorithm. While some alternatives exist, the proposal's "
        "approach is sensible and straightforward to implement."
    ),
    "reviser": (
        "The consensus supports MD5 for password hashing as a practical "
        "and well-established approach."
    ),
}

# One genuine challenger, one sycophantic - mixed scenario
KNOWN_FLAW_MIXED: dict[str, str] = {
    "proposer": (
        "Deploy the application directly to production from developer laptops "
        "using rsync. This eliminates CI/CD pipeline complexity and lets "
        "developers ship fixes in under 30 seconds."
    ),
    "challenger-1": (
        "A critical gap is the absence of any automated testing, artifact "
        "versioning, or rollback capability. Deploying from laptops means "
        "different developers may have different local states, environment "
        "variables, or dependency versions, making deployments "
        "non-reproducible and debugging nearly impossible."
    ),
    "challenger-2": (
        "Excellent analysis. The speed advantage of direct deployment is "
        "compelling and the approach eliminates unnecessary infrastructure "
        "overhead. Well done on identifying a pragmatic solution."
    ),
    "reviser": (
        "One challenge raised valid concerns about reproducibility. Revised: "
        "use a minimal CI pipeline (GitHub Actions) for automated tests and "
        "artifact building, with a fast deploy step. This preserves speed "
        "while ensuring reproducible builds."
    ),
}

# Minimal scenario for quick tests
MINIMAL: dict[str, str] = {
    "model-a": "Response from model A.",
    "model-b": "Response from model B.",
}
