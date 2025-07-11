"""File to visualize questions and their answers"""

import gradio as gr
import json

def load_json(file):
    if file is None:
        return [], {}, 0, 0
    try:
        with open(file.name, "r") as f:
            data = json.load(f)
        keys = list(data.keys())
        if not keys:
            return [], {}, 0, 0
        return keys, data, 0, len(keys)
    except Exception as e:
        return [], {}, 0, 0

def show_scene(keys, data, idx):
    if not keys or not data or idx < 0 or idx >= len(keys):
        return "", "", "", "", f"Scene 0 of 0"
    key = keys[idx]
    entry = data.get(key, {})
    prompt = entry.get("prompt", "")
    response = entry.get("response", "")
    correct = entry.get("correct_answer", "")
    score = entry.get("score", "")
    return prompt, response, correct, score, f"Scene {idx+1} of {len(keys)}: {key}"

def next_scene(idx, keys):
    if idx < len(keys) - 1:
        return idx + 1
    return idx

def prev_scene(idx):
    if idx > 0:
        return idx - 1
    return idx

with gr.Blocks() as demo:
    gr.Markdown("# QA Visualizer")
    file_input = gr.File(label="Select inference_results JSON file", file_types=[".json"])
    keys_state = gr.State([])
    data_state = gr.State({})
    idx_state = gr.State(0)
    total_state = gr.State(0)

    with gr.Row():
        prev_btn = gr.Button("Previous")
        next_btn = gr.Button("Next")
        scene_label = gr.Markdown("Scene 0 of 0")

    with gr.Row():
        gr.Markdown("**Prompt:**")
        prompt_box = gr.Textbox(label="", lines=4, interactive=False)
    with gr.Row():
        gr.Markdown("**Response:**")
        response_box = gr.Textbox(label="", lines=4, interactive=False)
    with gr.Row():
        gr.Markdown("**Correct Answer:**")
        correct_box = gr.Textbox(label="", lines=2, interactive=False)
    with gr.Row():
        gr.Markdown("**Score:**")
        score_box = gr.Textbox(label="", lines=1, interactive=False)

    def update_scene(idx, keys, data):
        return show_scene(keys, data, idx)

    file_input.change(
        fn=load_json,
        inputs=file_input,
        outputs=[keys_state, data_state, idx_state, total_state]
    ).then(
        fn=show_scene,
        inputs=[keys_state, data_state, idx_state],
        outputs=[prompt_box, response_box, correct_box, score_box, scene_label]
    )

    next_btn.click(
        fn=next_scene,
        inputs=[idx_state, keys_state],
        outputs=idx_state
    ).then(
        fn=update_scene,
        inputs=[idx_state, keys_state, data_state],
        outputs=[prompt_box, response_box, correct_box, score_box, scene_label]
    )

    prev_btn.click(
        fn=prev_scene,
        inputs=idx_state,
        outputs=idx_state
    ).then(
        fn=update_scene,
        inputs=[idx_state, keys_state, data_state],
        outputs=[prompt_box, response_box, correct_box, score_box, scene_label]
    )

if __name__ == "__main__":
    demo.launch(share=True)
