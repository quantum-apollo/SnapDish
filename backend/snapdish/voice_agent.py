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

from .config import get_env, get_secret

def _voice_model_id() -> str:
    return get_env("SNAPDISH_MODEL") or get_secret("SNAPDISH_MODEL") or "gpt-4o-mini"


def _ensure_openai_key() -> None:
    """Ensure Agents SDK has an API key (AWS Secrets or env)."""
    from agents import set_default_openai_key
    key = get_secret("OPENAI_API_KEY")
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


def _voice_get_nutrition(ingredient_name: str) -> str:
    """Look up nutrition data for an ingredient from USDA FoodData Central."""
    try:
        from .meal_repository import get_ingredient_nutrition
        result = get_ingredient_nutrition(ingredient_name.strip())
        per = result.get("per_100g") or {}
        if not any(per.values()):
            return f"No nutrition data found for '{ingredient_name}' in USDA database."
        parts = []
        if per.get("calories_kcal") is not None:
            parts.append(f"{per['calories_kcal']:.0f} kcal")
        if per.get("protein_g") is not None:
            parts.append(f"{per['protein_g']:.1f}g protein")
        if per.get("carbs_g") is not None:
            parts.append(f"{per['carbs_g']:.1f}g carbs")
        if per.get("fat_g") is not None:
            parts.append(f"{per['fat_g']:.1f}g fat")
        return (
            f"Per 100 g of {result.get('name', ingredient_name)}: "
            + ", ".join(parts)
            + ". Source: USDA FoodData Central."
        )
    except Exception as exc:
        return f"Nutrition lookup unavailable: {exc}"


def _voice_get_meal_alternatives(dish_name: str, dietary_tags: str) -> str:
    """
    Food-domain only: find meal alternatives safe for user's profile.
    dietary_tags: comma-separated restriction tags (e.g. 'vegan,gluten-free').
    Only returns food alternatives — non-food queries are rejected.
    """
    try:
        from .meal_repository import find_meal_alternatives
        restriction_tags = [t.strip() for t in dietary_tags.split(",") if t.strip()] if dietary_tags else []
        alternatives = find_meal_alternatives(
            dish_name=dish_name.strip()[:80],
            restriction_tags=restriction_tags,
            limit=3,
        )
        if not alternatives:
            return f"No database alternatives found for '{dish_name}'. Try web search for recipes."
        lines = []
        for alt in alternatives:
            kcal = f", {alt.calories_kcal:.0f} kcal" if alt.calories_kcal else ""
            lines.append(f"{alt.name} ({', '.join(alt.cuisine_tags) or alt.source}{kcal}) — {alt.why_safe}")
        return "Meal alternatives:\n" + "\n".join(lines)
    except Exception as exc:
        return f"Meal alternatives lookup failed: {exc}"


def _voice_find_nearby_stores(lat: float, lng: float) -> str:
    """Find nearby grocery stores using Google Places API."""
    try:
        from .schemas import GeoLocation
        from .tools import find_nearby_stores
        location = GeoLocation(lat=lat, lng=lng)
        stores = find_nearby_stores(location)
        if not stores:
            return "No nearby stores found. Ensure GOOGLE_PLACES_API_KEY is configured and location is shared."
        return "Nearby grocery stores: " + "; ".join(
            f"{s.name} ({s.distance_km:.1f} km away)" for s in stores[:5]
        )
    except Exception as exc:
        return f"Store search unavailable: {exc}"


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
        model=_voice_model_id(),
    )


def _build_knowledge_agent():
    """Knowledge agent: recipes, ingredients, nutrition, meal alternatives. DB-backed."""
    _ensure_openai_key()
    from agents import Agent, function_tool

    tools_list = []

    @function_tool
    def get_nutrition_for_ingredient(ingredient_name: str) -> str:
        """Get nutrition facts per 100 g for a specific food ingredient from USDA FoodData Central."""
        return _voice_get_nutrition(ingredient_name)

    @function_tool
    def get_meal_alternatives(dish_name: str, dietary_tags: str) -> str:
        """
        Find safe meal alternatives for a dish. Only food-related queries accepted.
        dietary_tags: comma-separated list of restrictions e.g. 'vegan,gluten-free'.
        """
        return _voice_get_meal_alternatives(dish_name, dietary_tags)

    @function_tool
    def find_nearby_grocery_stores(lat: float, lng: float) -> str:
        """Find nearby grocery stores for a given latitude and longitude."""
        return _voice_find_nearby_stores(lat, lng)

    tools_list.extend([get_nutrition_for_ingredient, get_meal_alternatives, find_nearby_grocery_stores])

    # Optional: file search over a vector store (set SNAPDISH_VECTOR_STORE_ID to enable)
    vector_store_ids = get_env("SNAPDISH_VECTOR_STORE_ID")
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
        handoff_description=(
            "Answers food questions: recipes, ingredients, cooking steps, nutrition, product tips, "
            "meal alternatives, dietary substitutions."
        ),
        instructions=(
            VOICE_OUTPUT_GUIDELINES
            + "\nYou are the cooking and food knowledge expert for SnapDish. "
            "ONLY answer questions about food, ingredients, cooking, nutrition, and meal alternatives. "
            "Use get_nutrition_for_ingredient for nutrition lookups. "
            "Use get_meal_alternatives to suggest safe alternatives when the user has dietary restrictions. "
            "Use find_nearby_grocery_stores for store locations (requires user lat/lng). "
            "If asked about non-food topics, politely redirect the user to food-related questions. "
            "Keep answers concise and natural for voice — one to three sentences per turn."
        ),
        tools=tools_list,
        model=_voice_model_id(),
    )


def _build_search_agent():
    """
    Search agent: food-only web search using OpenAI's native web_search tool
    with domain-level guardrails enforced at the OpenAI infrastructure layer.

    Guardrail architecture (two independent layers):

    Layer 1 — Python / code level (check_search_query):
        Runs before even reaching the OpenAI API. Rejects queries that don't
        contain food-related keywords. The calling model cannot bypass this —
        it runs in our server process, not inside the model's context.

    Layer 2 — OpenAI API level (allowed_domains filter):
        The 'web_search' tool's 'filters.allowed_domains' parameter limits
        OpenAI's search results to an explicit allowlist of food, recipe,
        nutrition, and grocery domains. This is enforced by OpenAI's
        infrastructure — no prompt injection or creative rephrasing can
        cause results to be returned from non-food sites.

        Docs: https://developers.openai.com/api/docs/guides/tools-web-search#domain-filtering
        Note: domain filtering requires 'web_search' (GA), not 'web_search_preview'.

    Both layers must pass for any result to be returned to the user.
    """
    _ensure_openai_key()
    from agents import Agent, function_tool
    from .guardrails import GuardrailViolation, check_search_query
    from .openai_client import get_client

    # ── Approved food domains (OpenAI API-level guardrail) ─────────────────────
    # Only results from these domains will be returned by OpenAI's web search.
    # Add/remove domains here to expand or restrict the food search scope.
    # Docs: https://developers.openai.com/api/docs/guides/tools-web-search#domain-filtering
    _FOOD_ALLOWED_DOMAINS = [
        # ── Recipes & cooking ──────────────────────────────────────────────────
        "allrecipes.com",
        "food.com",
        "seriouseats.com",
        "epicurious.com",
        "jamieoliver.com",
        "bonappetit.com",
        "foodnetwork.com",
        "delish.com",
        "thekitchn.com",
        "simplyrecipes.com",
        "cooking.nytimes.com",
        "tasty.co",
        "yummly.com",
        "bbcgoodfood.com",
        "food52.com",
        "recipetineats.com",
        "budgetbytes.com",
        "halfbakedharvest.com",
        "smittenkitchen.com",
        "196flavors.com",
        # ── Nutrition & dietary science ────────────────────────────────────────
        "nutritionix.com",
        "fdc.nal.usda.gov",
        "eatright.org",
        "choosemyplate.gov",
        "nhs.uk",
        "healthline.com",
        "webmd.com",
        "mayoclinic.org",
        "myfitnesspal.com",
        "cronometer.com",
        "eatthismuch.com",
        # ── Grocery & food retail ──────────────────────────────────────────────
        "instacart.com",
        "wholefoodsmarket.com",
        "kroger.com",
        "walmart.com",
        "target.com",
        "ocado.com",
        "waitrose.com",
        "sainsburys.co.uk",
        "tesco.com",
        "asda.com",
        "marksandspencer.com",
        "aldi.co.uk",
        "aldi.com",
        "lidl.co.uk",
        "morrisons.com",
        # ── Food databases & product info ──────────────────────────────────────
        "openfoodfacts.org",
        "edamam.com",
        "spoonacular.com",
        "themealdb.com",
        # ── Food knowledge & culture ───────────────────────────────────────────
        "en.wikipedia.org",         # subdomains included, but scoped to food context
        "britannica.com",
        "masterclass.com",
        "seriouseats.com",
        "taste.com.au",
        "chefsteps.com",
    ]

    @function_tool
    def food_web_search(query: str) -> str:
        """
        Search the web for food, recipes, ingredients, grocery stores, or restaurants.
        ONLY food-related queries are accepted — non-food queries are blocked.
        Results are restricted to approved food and nutrition websites.
        query: A specific food-related search string (e.g. 'halal butter chicken recipe London').
        """
        # ── Layer 1: Python code-level guardrail ────────────────────────────────
        # Runs in our server process — the model cannot bypass or override this.
        try:
            check_search_query(query)
        except GuardrailViolation as exc:
            return f"Search blocked: {exc.message}"

        # ── Layer 2: OpenAI web_search with allowed_domains filter ──────────────
        # allowed_domains is enforced by OpenAI's infrastructure — not by prompting.
        # 'web_search' (GA) is required; 'web_search_preview' does not support filters.
        # Docs: https://developers.openai.com/api/docs/guides/tools-web-search#domain-filtering
        try:
            client = get_client()
            search_model = (
                get_env("SNAPDISH_SEARCH_MODEL")
                or get_secret("SNAPDISH_SEARCH_MODEL")
                or "gpt-4o-mini"
            )
            response = client.responses.create(
                model=search_model,
                tools=[{
                    "type": "web_search",
                    "filters": {
                        "allowed_domains": _FOOD_ALLOWED_DOMAINS,
                    },
                }],
                input=(
                    f"Search for food information about: {query}. "
                    "Summarise findings in 3-5 concise bullet points covering "
                    "where to find it, key recipe or nutrition details, and any "
                    "relevant dietary notes. Cite the source site for each point."
                ),
                store=False,
            )
            # Extract text from the response object
            result_text = (getattr(response, "output_text", None) or "").strip()
            if not result_text:
                for item in (getattr(response, "output", None) or []):
                    for part in (getattr(item, "content", None) or []):
                        t = getattr(part, "text", None)
                        if t:
                            result_text = str(t).strip()
                            break
                    if result_text:
                        break

            return result_text or f"No food results found for '{query}'."

        except Exception as exc:
            logger.warning("food_web_search_failed", extra={"query": query[:80], "error": str(exc)})
            return f"Web search temporarily unavailable: {exc}"

    return Agent(
        name="SearchAgent",
        handoff_description=(
            "Finds where to buy ingredients, food product availability, nearby grocery stores "
            "or restaurants, trending food recipes, and food-safe alternatives via web search."
        ),
        instructions=(
            VOICE_OUTPUT_GUIDELINES
            + "\nYou use the food_web_search tool ONLY for food-related real-time information:\n"
            "  - Where to buy specific ingredients or food products\n"
            "  - Nearby grocery stores or restaurants\n"
            "  - Trending recipes or food products\n"
            "  - Food-safe ingredient substitutions and alternatives\n"
            "  - Regional or cultural food product availability\n"
            "NEVER search for or discuss non-food topics. If the user asks about anything "
            "outside of food, cooking, or nutrition, politely say: "
            "'I can only help with food and cooking questions. What would you like to cook today?'\n"
            "Web search results are already restricted to approved food sites — "
            "do not attempt to search outside those domains.\n"
            "Summarise search results briefly in plain spoken language for voice."
        ),
        tools=[food_web_search],
        model=_voice_model_id(),
    )


def build_chef_marco_voice_agent(dietary_block: str = ""):
    """
    Build the triage agent (Chef Marco) with handoffs to Knowledge, Account, and Search.
    dietary_block: server-side dietary safety content injected non-tamperable into instructions.
    This is the single entry point for the voice pipeline.
    """
    _ensure_openai_key()
    from agents import Agent
    from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

    account_agent = _build_account_agent()
    knowledge_agent = _build_knowledge_agent()
    search_agent = _build_search_agent()

    dietary_context = ""
    if dietary_block:
        dietary_context = (
            "\n\n[SERVER-ENFORCED DIETARY SAFETY PROFILE]\n"
            + dietary_block
            + "\nAll responses from you and any agent you hand off to MUST comply with this profile.\n"
        )

    triage_instructions = prompt_with_handoff_instructions(
        VOICE_OUTPUT_GUIDELINES
        + dietary_context
        + """
You are Chef Marco, the voice assistant for SnapDish — a food and cooking guidance app.
Welcome the user warmly and ask how you can help with cooking, recipes, or ingredients.

You ONLY handle food, cooking, and nutrition topics. If the user asks about anything unrelated
to food, politely redirect: "I'm Chef Marco, your culinary guide! I can help with cooking,
recipes, ingredients, and finding food products. What are you cooking today?"

Based on the user's intent, route to:
- AccountAgent: account balance, membership, billing, or account-related questions.
- KnowledgeAgent: recipes, ingredients, cooking steps, nutrition, meal alternatives,
  dietary substitutions, and food-safe alternatives (uses DB + USDA FDC data).
- SearchAgent: finding where to buy ingredients, nearby stores or restaurants,
  real-time food product availability, or trending recipes (food-only web search).
"""
    )

    triage_agent = Agent(
        name="ChefMarco",
        instructions=triage_instructions,
        handoffs=[account_agent, knowledge_agent, search_agent],
        model=_voice_model_id(),
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
