"""
This file takes a json file of model responses to a UPD subset, and has it get scored by an existing-llm API.
"""

import argparse
import json
import openai
import os

if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("Error: OPENAI_API_KEY environment variable is not set.")

def main():
    parser = argparse.ArgumentParser(description="Score model responses using an existing-llm API.")
    parser.add_argument("json_file", type=str, help="Path to the JSON file containing model responses.")
    parser.add_argument("--answer_key", type=str, help="Path to the answer key JSON file.", default=None)
    args = parser.parse_args()

    json_file = args.json_file

    # Load the JSON file into a Python dictionary
    with open(json_file, 'r') as f:
        data = json.load(f)

    # Read the scoring prompt from file
    with open('scoring_prompt.txt', 'r') as f:
        scoring_prompt = f.read()
 
    for item in data.items():
        point_cloud = item[0]
        current_prompt = scoring_prompt
        current_prompt += f"\nQUESTION:{item[1]["prompt"]}"
        if args.answer_key:
            with open(args.answer_key, 'r') as f:
                answer_key = json.load(f)
            if point_cloud in answer_key:
                correct_answer = f"\nCORRECT_ANSWER: {answer_key[point_cloud]}"
        else:
            correct_answer = f"\nCORRECT_ANSWER: The question is unanswerable, or none of the above."
        current_prompt += correct_answer
        current_prompt += f"\nMODEL_RESPONSE: {item[1]["response"]}"

        client = openai.OpenAI()

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": current_prompt}],
                max_tokens=10
            )
            generated_text = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error processing openai completion: {str(e)}")
            continue

        print(current_prompt)
        data[point_cloud]["correct_answer"] = correct_answer.replace("\nCORRECT_ANSWER: ", "")
        data[point_cloud]["score"] = generated_text

    # Create the output directory if it doesn't exist
    output_dir = "./scored_model_responses"
    os.makedirs(output_dir, exist_ok=True)

    #JSON file name with no path
    json_file_no_path = os.path.basename(os.path.normpath(json_file))

    with open(os.path.join(output_dir, json_file_no_path.replace('.json', '') + '_scored.json'), 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    main()