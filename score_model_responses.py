"""
This file takes a json file of model responses to a UPD subset, and has it get scored by an existing-llm API.
"""

import argparse
import json
import openai
import os

if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("Error: OPENAI_API_KEY environment variable is not set.")

def filename_uses_answer_key(path):
    """Return True if this response JSON should be graded against an answer key."""
    name = os.path.basename(path)
    return (
        name.endswith("standard.json")
        or "_aad_" in name
        or "_iasd_" in name
    )

def main():
    parser = argparse.ArgumentParser(description="Score model responses using an existing-llm API.")
    parser.add_argument("json_file", type=str, help="Path to the JSON file containing unscored model responses.")
    parser.add_argument("--answer_key", type=str, help="Path to the answer key JSON file.", default=None)
    args = parser.parse_args()

    json_file = args.json_file

    # Require answer_key for standard, AAD, and IASD subsets (including variants)
    if filename_uses_answer_key(json_file) and not args.answer_key:
        parser.error("--answer_key is required for standard, AAD, and IASD subset JSON files.")

    # Load the JSON file into a Python dictionary
    with open(json_file, 'r') as f:
        data = json.load(f)

    # Read the scoring prompt from file
    with open('scoring_prompt.txt', 'r') as f:
        scoring_prompt = f.read()
    
    # Define the model to use
    scoring_model = "gpt-4.1-mini"
    
    # Track if scoring failed
    scoring_failed = False

    answer_key = None
    if args.answer_key and filename_uses_answer_key(json_file):
        with open(args.answer_key, 'r') as f:
            answer_key = json.load(f)
 
    for item in data.items():
        point_cloud = item[0]
        current_prompt = scoring_prompt
        current_prompt += f"\nQUESTION:{item[1]["prompt"]}"
        if answer_key is not None and point_cloud in answer_key:
            correct_answer = f"\nCORRECT_ANSWER: {answer_key[point_cloud]}"
        else:
            correct_answer = f"\nCORRECT_ANSWER: The question is unanswerable, or none of the above."
        current_prompt += correct_answer
        current_prompt += f"\nMODEL_RESPONSE: {item[1]["response"]}"

        # If response is empty string, directly assign F and skip API call
        if item[1]["response"] == "":
            print(f"Empty response detected for {point_cloud}, assigning score='F' without API call")
            data[point_cloud]["correct_answer"] = correct_answer.replace("\nCORRECT_ANSWER: ", "")
            data[point_cloud]["score"] = "F"
            continue

        client = openai.OpenAI()

        max_attempts = 5
        for _ in range(max_attempts):
            try:
                response = client.chat.completions.create(
                    model=scoring_model,
                    messages=[{"role": "user", "content": current_prompt}],
                    max_completion_tokens=1
                )
                generated_text = response.choices[0].message.content.strip() if response.choices[0].message.content else ""
            except Exception as e:
                print(f"Error processing openai completion: {str(e)}")
                scoring_failed = True
                continue
            if generated_text not in ['T', 'F']:
                scoring_failed = True
            else:
                scoring_failed = False
                break

        print(current_prompt)
        print(f"Generated Text:<BEGIN>{generated_text}<END>")
        
        # Print detailed response information
        print(f"=== Response Details for {point_cloud} ===")
        print(f"Model: {response.model}")
        print(f"Finish Reason: {response.choices[0].finish_reason}")
        print(f"Usage - Prompt Tokens: {response.usage.prompt_tokens}")
        print(f"Usage - Completion Tokens: {response.usage.completion_tokens}")
        print(f"Usage - Total Tokens: {response.usage.total_tokens}")
        
        # Print reasoning tokens if available (GPT-5 models)
        if hasattr(response.usage, 'completion_tokens_details'):
            details = response.usage.completion_tokens_details
            if hasattr(details, 'reasoning_tokens'):
                print(f"Usage - Reasoning Tokens: {details.reasoning_tokens}")
            if hasattr(details, 'accepted_prediction_tokens'):
                print(f"Usage - Accepted Prediction Tokens: {details.accepted_prediction_tokens}")
            if hasattr(details, 'rejected_prediction_tokens'):
                print(f"Usage - Rejected Prediction Tokens: {details.rejected_prediction_tokens}")
        
        # Print the raw message object
        print(f"Raw Message Content: {response.choices[0].message.content}")
        print(f"Message Role: {response.choices[0].message.role}")
        print(f"=========================================\n")
        
        data[point_cloud]["correct_answer"] = correct_answer.replace("\nCORRECT_ANSWER: ", "")
        data[point_cloud]["score"] = generated_text

        if scoring_failed:
            print(f"ERROR: Invalid score '{generated_text}' for {point_cloud}")
            print(f"Expected 'T' or 'F', got: '{generated_text}'")
            print(f"Stopping scoring and saving with FAILED_ prefix")
            break

    # Create the output directory if it doesn't exist
    output_dir = "./scored_model_responses"
    os.makedirs(output_dir, exist_ok=True)

    # Get the folder name preceding the json file
    folder_name = os.path.basename(os.path.dirname(json_file))
    # Create the output folder inside scored_model_responses with scoring model name
    output_folder_name = f"{folder_name}_{scoring_model}"
    output_dir = os.path.join('scored_model_responses', output_folder_name)
    os.makedirs(output_dir, exist_ok=True)
    # Use the same json filename for the final file, but add model name before _scored
    base_filename = os.path.basename(json_file).replace('.json', '')
    if scoring_failed:
        output_filename = f"FAILED_{base_filename}_{scoring_model}_scored.json"
    else:
        output_filename = f"{base_filename}_{scoring_model}_scored.json"
    output_file = os.path.join(output_dir, output_filename)

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"\nScored responses saved to: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    main()
