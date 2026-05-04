"""Mock job source for local development and pipeline testing."""


def get_jobs() -> list[dict]:
    """Return realistic AI-related job listings as mock data."""
    return [
        {
            "company": "Neural Forge Labs",
            "title": "AI Agent Engineer",
            "location": "Remote (US)",
            "salary": "$120,000 - $150,000",
            "description": (
                "Build and ship autonomous AI workflows for go-to-market and operations teams. "
                "Own prompt strategy, eval pipelines, and agent reliability in production."
            ),
            "url": "https://neuralforgelabs.com/jobs/ai-agent-engineer",
            "source": "mock",
            "mock_score": 92,
        },
        {
            "company": "SignalCraft",
            "title": "Prompt Engineer, Applied AI",
            "location": "Hybrid (New York, NY)",
            "salary": "$105,000 - $135,000",
            "description": (
                "Design prompt architectures and retrieval pipelines for customer-facing AI tools. "
                "Partner with product and design to improve accuracy and tone."
            ),
            "url": "https://signalcraft.io/careers/prompt-engineer-applied-ai",
            "source": "mock",
            "mock_score": 85,
        },
        {
            "company": "Orbit Automations",
            "title": "Automation Engineer (LLM Systems)",
            "location": "Remote (Global)",
            "salary": "$95,000 - $125,000",
            "description": (
                "Create automation flows that combine APIs, workflow engines, and LLM reasoning. "
                "Focus on measurable business outcomes and resilient deployment practices."
            ),
            "url": "https://orbitautomations.com/jobs/automation-engineer-llm",
            "source": "mock",
            "mock_score": 78,
        },
        {
            "company": "Canvas Intelligence",
            "title": "Creative Technologist, AI Experiences",
            "location": "Hybrid (Los Angeles, CA)",
            "salary": "$110,000 - $140,000",
            "description": (
                "Prototype and productionize AI-driven creative experiences. "
                "Blend design sensibility with engineering execution across generative systems."
            ),
            "url": "https://canvasintelligence.com/careers/creative-technologist-ai",
            "source": "mock",
            "mock_score": 72,
        },
    ]
