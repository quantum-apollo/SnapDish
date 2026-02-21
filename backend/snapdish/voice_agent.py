"""
Chef Marco voice agent for real-time voice with the OpenAI Agents SDK.

Multi-agent setup:
- Triage Agent (Chef Marco): routes to Knowledge, Account, or Search.
- Knowledge Agent: recipes, ingredients, product tips (optional vector store).
- Account Agent: account balance, membership (stub).
- Search Agent: web search for locations for food products, where to buy, trending.

Uses VoicePipeline: mic → STT → agent → TTS → speaker.
See: https://developers.openai.com/cookbook/examples/agents_sdk/app_assistant_voice_agents
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _ensure_openai_key() -> None:
    """Ensure Agents SDK has an API key (from env or set_default_openai_key)."""
    from agents import set_default_openai_key
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        set_default_openai_key(key)


# --- Shared voice output guidelines for all agents ---
VOICE_OUTPUT_GUIDELINES = """
[Output structure]
Your output will be delivered as spoken audio. Follow these guidelines:
1. Use a friendly, warm tone that sounds natural when spoken aloud.
2. Keep responses short—one to three concise sentences per turn when possible.
3. Avoid long lists and bullet points; summarize or offer to go step by step.
4. Use plain language; no jargon. Light Italian flavor is fine (bene, allora, perfetto).
"""


def _get_account_info_stub(user_id: str) -> str:
    """Return dummy account info for voice (stub)."""
    return (
        f"For user {user_id}: account balance is 72.50 pounds, "
        "membership is Gold Executive. In production, this would come from your account system."
    )


def _get_nutrition_estimate() -> str:
    """Return a short nutrition disclaimer for voice (stub)."""
    return (
        "Nutrition estimates aren't computed in this demo. "
        "For accurate macros, use a nutrition database or scale your ingredients."
    )


def _find_nearby_stores(lat: float, lng: float) -> str:
    """Return nearby store suggestions (stub)."""
    return (
        "Store search is a stub for now. In the app you'll see nearby grocery suggestions "
        "when you share your location. For real-time store locations, the Search agent can look up the web."
    )


def _build_account_agent():
    """Account agent: balance, membership, user info."""
    _ensure_openai_key()
    from agents import Agent, function_tool

    @function_tool
    def get_account_info(user_id: str) -> str:
        """Return account info for the given user ID (balance, membership)."""
        return _get_account_info_stub(user_id)

    return Agent(
        name="AccountAgent",
        handoff_description="Handles account balance, membership, and user account questions.",
        instructions=(
            VOICE_OUTPUT_GUIDELINES
            + "\nYou provide account information (balance, membership) using the get_account_info tool. "
            "Keep answers brief and friendly for voice."
        ),
        tools=[get_account_info],
        model=os.environ.get("SNAPDISH_MODEL", "gpt-4o-mini"),
    )


def _build_knowledge_agent():
    """Knowledge agent: recipes, ingredients, product tips. Optional vector store."""
    _ensure_openai_key()
    from agents import Agent, function_tool

    tools_list = []

    @function_tool
    def get_nutrition_estimate() -> str:
        """Get a brief nutrition disclaimer for the current dish or ingredients."""
        return _get_nutrition_estimate()

    @function_tool
    def find_nearby_stores(lat: float, lng: float) -> str:
        """Find nearby grocery stores for a given latitude and longitude."""
        return _find_nearby_stores(lat, lng)

    tools_list.extend([get_nutrition_estimate, find_nearby_stores])

    # Optional: file search over a vector store (set SNAPDISH_VECTOR_STORE_ID to enable)
    vector_store_ids = os.environ.get("SNAPDISH_VECTOR_STORE_ID")
    if vector_store_ids:
        from agents import FileSearchTool
        tools_list.append(
            FileSearchTool(
                max_num_results=3,
                vector_store_ids=[vsid.strip() for vsid in vector_store_ids.split(",")],
            )
        )

    return Agent(
        name="KnowledgeAgent",
        handoff_description="Answers about recipes, ingredients, cooking steps, product tips, and food knowledge.",
        instructions=(
            VOICE_OUTPUT_GUIDELINES
            + "\nYou are the cooking and product knowledge expert for SnapDish. "
            "Answer questions about recipes, ingredients, prep, cooking steps, and product info. "
            "Use tools when needed. Keep answers concise for voice."
        ),
        tools=tools_list,
        model=os.environ.get("SNAPDISH_MODEL", "gpt-4o-mini"),
    )


def _build_search_agent():
    """Search agent: web search for locations, where to buy, trending, real-time info."""
    _ensure_openai_key()
    from agents import Agent, WebSearchTool

    return Agent(
        name="SearchAgent",
        handoff_description="Finds locations for food products, where to buy ingredients, stores, and real-time or trending info via web search.",
        instructions=(
            VOICE_OUTPUT_GUIDELINES
            + "\nYou use web search to find real-time information: "
            "locations for food products, where to buy specific ingredients, nearby stores, "
            "trending recipes or products, and similar. Summarize results briefly for voice."
        ),
        tools=[WebSearchTool()],
        model=os.environ.get("SNAPDISH_MODEL", "gpt-4o-mini"),
    )


def build_chef_marco_voice_agent():
    """
    Build the triage agent (Chef Marco) with handoffs to Knowledge, Account, and Search.
    This is the single entry point for the voice pipeline.
    """
    _ensure_openai_key()
    from agents import Agent
    from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

    account_agent = _build_account_agent()
    knowledge_agent = _build_knowledge_agent()
    search_agent = _build_search_agent()

    triage_instructions = prompt_with_handoff_instructions(
        VOICE_OUTPUT_GUIDELINES
        + """
You are Chef Marco, the voice assistant for SnapDish. Welcome the user and ask how you can help.

Based on the user's intent, route to:
- AccountAgent: account balance, membership, user ID, billing, or account-related questions.
- KnowledgeAgent: recipes, ingredients, cooking steps, product tips, substitutions, food knowledge (no real-time web needed).
- SearchAgent: locations for food products, where to buy something, nearby stores, real-time or trending info, or anything that needs current web search.
"""
    )

    triage_agent = Agent(
        name="ChefMarco",
        instructions=triage_instructions,
        handoffs=[account_agent, knowledge_agent, search_agent],
        model=os.environ.get("SNAPDISH_MODEL", "gpt-4o-mini"),
    )
    return triage_agent


def get_voice_pipeline_config():
    """TTS config so Chef Marco sounds warm and natural (optional)."""
    from agents.voice import TTSModelSettings, VoicePipelineConfig
    custom_tts = TTSModelSettings(
        instructions=(
            "Personality: warm, friendly cooking coach. "
            "Tone: Clear and reassuring, like a skilled home chef helping a friend. "
            "Pronunciation: Clear and steady, with a slight Italian warmth. "
            "Tempo: Moderate; brief pauses after tips or questions. "
            "Emotion: Encouraging and supportive."
        )
    )
    return VoicePipelineConfig(tts_settings=custom_tts)
