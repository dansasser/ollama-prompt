import ollama
import argparse
import json

def main():
    parser = argparse.ArgumentParser(description="Send a prompt to local Ollama and get full verbose JSON response (just like PowerShell).")
    parser.add_argument('--prompt', required=True, help="Prompt to send to the model")
    parser.add_argument('--model', default="deepseek-v3.1:671b-cloud", help="Model name")
    parser.add_argument('--temperature', type=float, default=0.1, help="Sampling temperature")
    parser.add_argument('--max_tokens', type=int, default=2048, help="Max tokens for response")
    args = parser.parse_args()

    result = ollama.generate(
        model=args.model,
        prompt=args.prompt,
        options={
            "temperature": args.temperature,
            "num_predict": args.max_tokens
        },
        stream=False
    )

    # Convert Pydantic to dict (matches PowerShell's ConvertTo-Json)
    result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    print(json.dumps(result_dict, indent=2))

if __name__ == "__main__":
    main()
