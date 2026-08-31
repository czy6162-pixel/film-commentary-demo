import json
import re
import urllib.error
import urllib.request


def chat_completions_url(base_url):
    url = base_url.strip().rstrip("/")
    return url if url.endswith("/chat/completions") else f"{url}/chat/completions"


def extract_json(text):
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def build_request_payload(storyboard, prompts, model):
    compact = {
        "shots": [
            {
                "shot_id": shot["shot_id"],
                "visual": shot["visual"],
                "shot_size": shot["shot_size"],
                "camera_angle": shot["camera_angle"],
                "camera_movement": shot["camera_movement"],
                "narration": shot["narration"],
            }
            for shot in storyboard["shots"]
        ],
        "prompts": prompts["prompts"],
    }
    instruction = (
        "Improve the narration and AI image/video prompts for the supplied storyboard. "
        "Keep every shot_id unchanged. Keep narration in its original language. "
        "Vary composition, motion and negative prompts according to each shot. "
        "Return JSON only with this shape: "
        '{"shots":[{"shot_id":"...","narration":"..."}],'
        '"prompts":[{"shot_id":"...","image_prompt":"...",'
        '"video_prompt":"...","negative_prompt":"..."}]}.\n\n'
        + json.dumps(compact, ensure_ascii=False)
    )
    return {
        "model": model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": "You are a film pre-production assistant that returns valid JSON only."},
            {"role": "user", "content": instruction},
        ],
    }


def apply_enhancement(storyboard, prompts, response_data):
    shot_by_id = {shot["shot_id"]: shot for shot in storyboard["shots"]}
    prompt_by_id = {prompt["shot_id"]: prompt for prompt in prompts["prompts"]}
    for item in response_data.get("shots", []):
        shot_id = item.get("shot_id")
        narration = str(item.get("narration", "")).strip()
        if shot_id in shot_by_id and narration:
            shot_by_id[shot_id]["narration"] = narration
    for item in response_data.get("prompts", []):
        shot_id = item.get("shot_id")
        if shot_id not in prompt_by_id:
            continue
        for field in ("image_prompt", "video_prompt", "negative_prompt"):
            value = str(item.get(field, "")).strip()
            if value:
                prompt_by_id[shot_id][field] = value
    storyboard["narration_generation"]["mode"] = "api_enhanced"
    prompts["generation_mode"] = "api_enhanced"
    return storyboard, prompts


def enhance_with_api(storyboard, prompts, base_url, api_key, model, timeout=45):
    request = urllib.request.Request(
        chat_completions_url(base_url),
        data=json.dumps(build_request_payload(storyboard, prompts, model), ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"API request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API request failed: {exc.reason}") from exc
    try:
        content = raw["choices"][0]["message"]["content"]
        response_data = extract_json(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("API returned an unsupported response format.") from exc
    return apply_enhancement(storyboard, prompts, response_data)

