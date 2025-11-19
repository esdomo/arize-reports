import json
import sys

def extract_conversation(json_data):
    """Extracts readable message interactions from the JSON conversation log."""
    messages = json_data.get("messages", [])
    output = []

    for msg in messages:
        role = msg.get("type")
        content = (msg.get("content") or "").strip()

        # Skip empty or tool-type messages
        if not content or role not in ("human", "ai"):
            continue

        role_name = "Human" if role == "human" else "AI"
        output.append(f"{role_name}:\n{content}\n")

    return "\n".join(output)


def main():
    """Reads JSON from stdin or a file path and prints extracted conversation."""
    if len(sys.argv) > 1:
        # Read from a file
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        # Read from stdin
        data = json.load(sys.stdin)

    transcript = extract_conversation(data)
    print("\n--- Conversation Transcript ---\n")
    print(transcript)


if __name__ == "__main__":
    main()
