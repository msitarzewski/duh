# Competitive Landscape Analysis

**Date**: 2026-02-15
**Purpose**: Understand what exists, what's been attempted, and where "duh" fits in the landscape.

---

## 1. Multi-Model Orchestration Frameworks

### LangGraph (LangChain)
- **What**: Graph-based workflow orchestration for LLM agents
- **Multi-provider**: Supports multiple providers via LangChain abstractions
- **Debate/consensus**: No. Agents coordinate tasks, don't debate
- **Persistent memory**: Limited (checkpointing, not knowledge accumulation)
- **Federated**: No
- **Status**: Most widely used agentic framework as of 2025-2026
- **Sources**: https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen

### CrewAI
- **What**: Role-based multi-agent coordination (inspired by org structures)
- **Multi-provider**: Supports multiple providers
- **Debate/consensus**: No. Agents have roles and collaborate, don't challenge each other
- **Persistent memory**: Basic memory features, not knowledge accumulation
- **Federated**: No
- **Status**: Active, growing adoption
- **Sources**: https://o-mega.ai/articles/langgraph-vs-crewai-vs-autogen-top-10-agent-frameworks-2026

### AutoGen (Microsoft)
- **What**: Conversational multi-agent framework
- **Multi-provider**: Supports multiple providers
- **Debate/consensus**: Conversational collaboration, not structured consensus
- **Persistent memory**: Limited
- **Federated**: No
- **Status**: Active, v2.1.0, research-driven
- **Sources**: https://www.getmaxim.ai/articles/top-5-ai-agent-frameworks-in-2025-a-practical-guide-for-ai-builders/

### MetaGPT
- **What**: Multi-agent software development (predefined dev workflow agents)
- **Multi-provider**: Limited
- **Debate/consensus**: No. Follows predefined workflow roles
- **Persistent memory**: No
- **Federated**: No
- **Status**: Active, 92% accuracy on multi-step coding tasks
- **Sources**: https://www.turing.com/resources/ai-agent-frameworks

### Graph-of-Agents (GoA) — 2026
- **What**: Framework using node sampling and edge construction to select relevant agents
- **Notable**: 89.4% accuracy on MMLU-Pro using only three agents
- **Sources**: https://dasroot.net/posts/2026/02/multi-agent-multi-llm-systems-future-ai-architecture-guide-2026/

### Assessment
These are **workflow tools**, not **thinking infrastructure**. They coordinate tasks across agents but don't produce collective knowledge, don't preserve dissent, and don't accumulate decisions over time. None have federated knowledge sharing.

---

## 2. Mixture-of-Agents (MoA)

### Together AI — MoA Paper (ICLR 2025)
- **What**: Layered system where LLMs in each layer receive outputs from all models in the previous layer and synthesize improved responses
- **Architecture**: Proposers (generate diverse responses) + Aggregators (synthesize). Multiple layers.
- **Models used**: Six open-source models (Qwen1.5 110B/72B, WizardLM-8x22B, LLaMA-3-70B, Mixtral-8x22B, dbrx-instruct)
- **Key finding**: LLMs produce better outputs when given other models' outputs as context, even from weaker models ("collaborativeness")
- **Results**: Beat GPT-4o on AlpacaEval 2.0 using only open-source models (+7.6% absolute improvement)
- **Limitations**: High latency (models wait for previous layer). Stateless. No memory. No knowledge accumulation. No federated sharing. Loses the debate in synthesis.
- **Status**: Research paper, not a product
- **Sources**: https://arxiv.org/html/2406.04692v1

### Assessment
**MoA validates the core thesis**: multi-model collaboration produces better results than any single model. But it's stateless and ephemeral — every query starts from scratch. "duh" would take MoA's insight and add persistent memory, knowledge accumulation, dissent preservation, and network effects.

---

## 3. Multi-Agent Debate Research

### Improving Factuality through Multiagent Debate (Du et al., 2023)
- **What**: Foundational paper showing multiple LLM agents debating improves factuality and reasoning
- **Sources**: https://arxiv.org/abs/2305.14325

### Adaptive Heterogeneous Multi-Agent Debate (2025)
- **What**: Agents with distinct roles debate and reach consensus
- **Results**: 4-6% higher accuracy, 30% fewer factual errors
- **Sources**: https://link.springer.com/article/10.1007/s44443-025-00353-3

### Encouraging Divergent Thinking through Multi-Agent Debate (EMNLP 2024)
- **What**: Focuses on producing diverse perspectives rather than converging to single answer
- **Sources**: https://aclanthology.org/2024.emnlp-main.992/

### Multi-Agent Debate Evaluation (ICLR Blog 2025)
- **What**: Evaluation of five MAD frameworks on nine benchmarks
- **Finding**: Current MAD frameworks "fail to consistently outperform simple single-agent test-time computation strategies"
- **Implication**: The field is still developing. Debate helps for factuality but naive implementations don't always beat a single strong model thinking longer
- **Sources**: https://d2jud02ci9yv69.cloudfront.net/2025-04-28-mad-159/blog/mad/

### Multi-Agent Debate for LLM Judges with Adaptive Stability Detection (2025)
- **What**: Debate system with adaptive stopping when consensus stabilizes
- **Sources**: https://arxiv.org/html/2510.12697v1

### Assessment
Academic research validates that debate improves quality, especially for factuality. But **all implementations are research prototypes**, not products. None have persistent memory, knowledge accumulation, federated sharing, or outcome tracking. The honest caveat: naive debate doesn't always beat a single strong model, so the consensus protocol design matters — forced disagreement, devil's advocate, and structured challenge phases are important.

---

## 4. AI Research & Fact-Checking Tools

### Perplexity AI
- **What**: Answer engine with web citations
- **Multi-model**: Single provider (their own + partnerships)
- **Provenance**: Shows sources/citations
- **Memory**: Session-based, no cross-session accumulation
- **Network**: Centralized
- **Sources**: https://deepresearcher.site/blog/best-ai-tools-deep-research-2025

### Consensus.app
- **What**: Searches peer-reviewed papers, shows supporting/opposing evidence
- **Multi-model**: Single provider
- **Provenance**: Links to papers
- **Memory**: No persistent knowledge accumulation
- **Network**: Centralized
- **Sources**: https://www.dip-ai.com/use-cases/en/the-best-automated-research-synthesis

### Elicit
- **What**: Research assistant for systematic literature reviews (125M+ papers)
- **Multi-model**: Single provider
- **Provenance**: Paper citations and data extraction
- **Memory**: Project-based, not accumulating knowledge
- **Network**: Centralized
- **Sources**: https://www.documind.chat/blog/ai-research-assistant

### FACT-AUDIT (ACL 2025)
- **What**: Multi-agent fact-checking framework with adaptive agents
- **Multi-model**: Multi-agent, unclear on multi-provider
- **Status**: Research paper, not a product
- **Sources**: https://aclanthology.org/2025.acl-long.17.pdf

### VERIFAID (2025)
- **What**: RAG-based fact-checking with dynamically growing knowledge base
- **Notable**: Closest to knowledge accumulation concept — builds a scalable knowledge base
- **Limitation**: Single-instance, not federated
- **Sources**: https://www.sciencedirect.com/science/article/pii/S0045790625006895

### Multi-Agent Misinformation Lifecycle (ICWSM 2025)
- **What**: Specialized agents for indexing, classifying, extracting, correcting, and verifying misinformation
- **Notable**: Covers full lifecycle with dedicated agent roles
- **Sources**: https://workshop-proceedings.icwsm.org/pdf/2025_24.pdf

### Assessment
These tools **answer questions** or **verify claims**. They don't accumulate knowledge across sessions, share it between instances, or produce a browsable knowledge base with debate provenance. VERIFAID's growing knowledge base is the closest concept but remains single-instance and single-provider.

---

## 5. Federated / Decentralized Knowledge Systems

### Orchestrated Distributed Intelligence (2025 paper)
- **What**: Proposes central orchestration of distributed AI agents with feedback loops
- **Architecture**: Central orchestration layer, multi-loop feedback, emergence-based design
- **Knowledge sharing**: Theoretical. No implementation, no shared memory protocol
- **Status**: Academic paper, conceptual framework
- **Sources**: https://arxiv.org/html/2503.13754v2

### Federated Learning (broad field)
- **Market**: $150M in 2023, projected $2.3B by 2032
- **What**: Collaborative model training without sharing raw data
- **Key distinction**: Shares model weights/gradients, NOT knowledge/decisions between LLM instances
- **Sources**: https://en.wikipedia.org/wiki/Federated_learning

### Blockchain + AI Systems
- **What**: Decentralized compute marketplaces, model training verification
- **Key distinction**: Focus on compute/training, not knowledge sharing
- **Sources**: https://www.mdpi.com/2078-2489/16/9/765

### Assessment
**The federated knowledge sharing concept appears novel.** Federated learning shares model weights. Blockchain+AI shares compute. Nobody is building a network where AI instances share *decisions and their reasoning* across a federated protocol. The navigator node concept — lightweight index of "who solved what, how, and what happened" — has no direct precedent found.

---

## 6. Gap Analysis: What "duh" Would Uniquely Provide

| Capability | Best Existing | Gap |
|---|---|---|
| Multi-model collaboration | MoA (research) | No product. Stateless. |
| Structured debate | Academic papers | No product. No memory. |
| Multi-provider consensus | Nothing found | Novel combination |
| Local model first-class | Limited in frameworks | Novel emphasis |
| Persistent knowledge accumulation | VERIFAID (single instance) | No federated version |
| Federated knowledge sharing | Nothing found | Novel |
| Navigator nodes (knowledge index) | Nothing found | Novel |
| Dissent preservation | Nothing found | Novel |
| Outcome tracking on decisions | Nothing found | Novel |
| Browsable knowledge base with provenance | Nothing found | Novel |
| Domain-agnostic (not dev-only) | Perplexity (single model) | Novel in multi-model context |
| Knowledge democratization (local models access network intelligence) | Nothing found | Novel |

### The Honest Summary

**Individual pieces are validated:**
- Multi-model collaboration improves output quality (MoA, ICLR 2025)
- Debate between models improves factuality (multiple papers, 2023-2025)
- Federated architectures scale (federated learning, proven at scale)
- Knowledge accumulation has value (VERIFAID, Elicit)

**Nobody has assembled the full stack:**
Multi-provider consensus + persistent knowledge + federated sharing + outcome tracking + browsable knowledge base with debate provenance

**Risks to monitor:**
- MAD frameworks don't consistently beat single strong models (ICLR 2025 blog). Consensus protocol design matters — naive "ask three models and merge" is insufficient.
- Sycophancy in models may produce false consensus. Forced disagreement and devil's advocate roles are essential.
- Cost multiplication from multi-model calls needs transparent tracking.
- Federated knowledge quality control is an unsolved problem at scale.

---

## 7. Key Papers and References

| Reference | Relevance | URL |
|---|---|---|
| MoA (Together AI, ICLR 2025) | Validates multi-model collaboration | https://arxiv.org/html/2406.04692v1 |
| Multiagent Debate for Factuality (Du et al., 2023) | Validates debate improves reasoning | https://arxiv.org/abs/2305.14325 |
| Adaptive Heterogeneous MAD (2025) | Diverse agent roles in debate | https://link.springer.com/article/10.1007/s44443-025-00353-3 |
| MAD Evaluation (ICLR Blog 2025) | Honest assessment of debate limitations | https://d2jud02ci9yv69.cloudfront.net/2025-04-28-mad-159/blog/mad/ |
| Orchestrated Distributed Intelligence (2025) | Conceptual framework for agent coordination | https://arxiv.org/html/2503.13754v2 |
| FACT-AUDIT (ACL 2025) | Multi-agent fact-checking | https://aclanthology.org/2025.acl-long.17.pdf |
| VERIFAID (2025) | Growing knowledge base for fact-checking | https://www.sciencedirect.com/science/article/pii/S0045790625006895 |
| Multi-Agent Multi-LLM Guide (2026) | Current state of the art overview | https://dasroot.net/posts/2026/02/multi-agent-multi-llm-systems-future-ai-architecture-guide-2026/ |
