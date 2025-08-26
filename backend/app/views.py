import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .utils import (
    sanitize_item_name,
    build_prompt,
    mock_generate,
    call_openai,
    check_rate_limit,
    call_deepseek,
    call_serpapi_for_upsell,
)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


@csrf_exempt  # simplified for take-home; in prod use proper auth/CSRF
def generate_item_details(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    ip = _client_ip(request)
    if not check_rate_limit(ip):
        return JsonResponse({"detail": "Rate limit exceeded. Try later."}, status=429)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)

    item_name = payload.get("itemName", "")
    mode = (payload.get("mode") or "mock").lower()        # "mock", "openai", "deepseek"
    model_choice = (payload.get("model") or "gpt-4").lower()

    try:
        item_name = sanitize_item_name(item_name)
    except ValueError as e:
        return JsonResponse({"detail": str(e)}, status=400)

    sys_prompt, user_prompt = build_prompt(item_name)

    try:
        if mode == "openai":
            model_name = "gpt-3.5-turbo" if "3.5" in model_choice else "gpt-4o-mini"
            description, upsell = call_openai(sys_prompt, user_prompt, model_name)
            model_used = f"openai-{model_name}"

        # elif mode == "deepseek":
        #     # common DeepSeek chat models: "deepseek-chat" (general), "deepseek-coder" (coding)
        #     model_name = "deepseek-chat"
        #     description, upsell = call_deepseek(sys_prompt, user_prompt, model_name)
        #     model_used = f"deepseek-{model_name}"

        elif mode == "serpapi":
        # Generate desc via mock (≤30 words), but compute upsell via SerpAPI
            description, _ = mock_generate(item_name, model_choice)
            upsell = call_serpapi_for_upsell(item_name)
            model_used = "serpapi+mock-desc"

        else:
            description, upsell = mock_generate(item_name, model_choice)
            model_used = f"mock-{model_choice}"

    except Exception:
        # any failure falls back to mock so the UI still works
        description, upsell = mock_generate(item_name, model_choice)
        model_used = f"mock-{model_choice}"

    return JsonResponse(
        {
            "itemName": item_name,
            "model": model_used,
            "description": description,
            "upsell": upsell,
            "meta": {"wordCount": len(description.split())},
        },
        status=200,
    )
