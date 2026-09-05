import json


MAX_ACTIVE_ENTITIES = 12


def empty_active_context():
    return {
        "topic": None,
        "last_entity_key": None,
        "latest_reference": None,
        "entities": [],
    }


def normalize_active_context(value):
    if not isinstance(value, dict):
        return empty_active_context()

    topic = value.get("topic")
    if topic is not None:
        topic = str(topic).strip() or None

    last_entity_key = value.get("last_entity_key")
    if last_entity_key is not None:
        last_entity_key = str(last_entity_key).strip() or None

    raw_entities = value.get("entities", [])
    entities = []
    seen_keys = set()

    if isinstance(raw_entities, list):
        for raw in raw_entities:
            if not isinstance(raw, dict):
                continue

            key = str(raw.get("key", "")).strip()
            if not key or key in seen_keys:
                continue

            role = raw.get("role")
            if role is not None:
                role = str(role).strip() or None

            description = raw.get("description")
            if description is not None:
                description = str(description).strip() or None

            aliases = raw.get("aliases", [])
            clean_aliases = []
            if isinstance(aliases, list):
                for alias in aliases:
                    alias = str(alias).strip()
                    if alias and alias not in clean_aliases:
                        clean_aliases.append(alias)

            entities.append(
                {
                    "key": key,
                    "role": role,
                    "description": description,
                    "aliases": clean_aliases[:8],
                }
            )
            seen_keys.add(key)

            if len(entities) >= MAX_ACTIVE_ENTITIES:
                break

    valid_keys = {item["key"] for item in entities}

    if last_entity_key not in valid_keys:
        last_entity_key = None

    latest_reference = value.get("latest_reference")
    if not isinstance(latest_reference, dict):
        latest_reference = None
    else:
        surface = str(latest_reference.get("surface", "")).strip()
        entity_key = str(latest_reference.get("entity_key", "")).strip()

        if not surface or entity_key not in valid_keys:
            latest_reference = None
        else:
            latest_reference = {
                "surface": surface,
                "entity_key": entity_key,
            }

    return {
        "topic": topic,
        "last_entity_key": last_entity_key,
        "latest_reference": latest_reference,
        "entities": entities,
    }


def format_active_context(context):
    context = normalize_active_context(context)

    lines = []

    if context["topic"]:
        lines.append(f"Current topic: {context['topic']}")
    else:
        lines.append("Current topic: (none)")

    if context["last_entity_key"]:
        lines.append(
            f"Last referenced entity: {context['last_entity_key']}"
        )

    latest_reference = context["latest_reference"]
    if latest_reference:
        lines.append(
            "Latest reference resolution: "
            f"{latest_reference['surface']} -> "
            f"{latest_reference['entity_key']}"
        )

    if context["entities"]:
        lines.append("Active entities:")

        for entity in context["entities"]:
            details = [entity["key"]]

            if entity["role"]:
                details.append(f"role={entity['role']}")

            if entity["description"]:
                details.append(
                    f"description={entity['description']}"
                )

            if entity["aliases"]:
                details.append(
                    "aliases=" + ", ".join(entity["aliases"])
                )

            lines.append("- " + " | ".join(details))
    else:
        lines.append("Active entities: (none)")

    return "\n".join(lines)


def active_context_to_json(context):
    return json.dumps(
        normalize_active_context(context),
        ensure_ascii=False,
        separators=(",", ":"),
    )
