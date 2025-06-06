"""A utility from AdvDL spring 2025. This script runs with a working installation of MiniGPT-3D. There is no need to run it unless you want to."""

import argparse
import torch
import gradio as gr
from transformers import StoppingCriteriaList
from minigpt4.common.config import Config
from minigpt4.common.registry import registry
from minigpt4.conversation.conversation import Chat, CONV_VISION_Vicuna0, CONV_VISION_LLama2, CONV_VISION, \
    StoppingCriteriaSub
import os
import json

def parse_args():
    parser = argparse.ArgumentParser(description="Demo")
    parser.add_argument("--cfg-path", default="./eval_configs/MiniGPT_3D_conv_UI_demo.yaml",
                        help="path to configuration file.")
    parser.add_argument("--gpu-id", type=int, default=0, help="specify the gpu to load the model.")
    parser.add_argument(
        "--options",
        nargs="+",
        help="override some settings in the used config, the key-value pair "
             "in xxx=yyy format will be merged into config file (deprecate), "
             "change to --cfg-options instead.",
    )
    args = parser.parse_args()
    return args

# ========================================
#             Model Initialization
# ========================================

conv_dict = {'pretrain_vicuna0': CONV_VISION_Vicuna0,
             'pretrain_llama2': CONV_VISION_LLama2,
             'pretrain': CONV_VISION}

print('Initializing Chat')
args = parse_args()
cfg = Config(args)

model_config = cfg.model_cfg
model_config.device_8bit = args.gpu_id
model_cls = registry.get_model_class(model_config.arch)
model = model_cls.from_config(model_config).to('cuda:{}'.format(args.gpu_id))

CONV_VISION = conv_dict[model_config.model_type]

stop_words_ids = [[835], [2277, 29937]]
stop_words_ids = [torch.tensor(ids).to(device='cuda:{}'.format(args.gpu_id)) for ids in stop_words_ids]
stopping_criteria = StoppingCriteriaList([StoppingCriteriaSub(stops=stop_words_ids)])

chat = Chat(model, device='cuda:{}'.format(args.gpu_id), stopping_criteria=stopping_criteria)
print('Initialization Finished, you can chat with me using the below link!!!!')

names_list = []
upd_subset_type = None #string for writing the inference results file name
upd_version_name = None #string for writing the inference results file name

class FakeUpload:
    """
    A simple container class to mimic file upload objects for point cloud inference.
    The original MiniGPT-3D gradio code this file is based on only ever used file
    upload objects, so this class substitutes for that to allow programmatic evaluation that does not require those file upload objects that come from the gradio UI.
    """
    def __init__(self, path, hex, scene_name):
        self.name = path
        self.hex = hex
        self.scene_name = scene_name

def process_txt(file):
    global names_list
    global upd_version_name
    with open(file.name, 'r') as f:
        names_list = f.read().splitlines()
    upd_version_name = os.path.basename(os.path.normpath(file.name)).replace('.txt', '')
    return "\n".join(names_list)

def make_named_upd_txt_files(names, dir_path):
    return [os.path.join(dir_path, name + ".txt") for name in names]

def make_named_ply_files(names, dir_path):
    results = []
    for name in names:
        folder_name = name.split('@')
        folder = folder_name[0]
        scene_name = folder_name[1]
        results.append(FakeUpload(os.path.join(dir_path, folder, scene_name, scene_name + ".ply"), folder, scene_name))
    return results

def inference(pc_path, txt_path, num_beams, temperature, max_new_tokens, max_length, min_length):
    global names_list
    global upd_subset_type
    if not os.path.isdir(pc_path):
        return f"Error: '{pc_path}' is not a valid folder path."
    if not os.path.isdir(txt_path):
        return f"Error: '{txt_path}' is not a valid folder path."
    pc_ply_list = make_named_ply_files(names_list, pc_path)
    upd_txt_file_list = make_named_upd_txt_files(names_list, txt_path)
    upd_subset_type = os.path.basename(os.path.normpath(txt_path))
    if not upd_txt_file_list or not pc_ply_list:
        return "[ERROR] upd_txt_file_list or pc_ply_list is empty. Please process the input files first."
    results = {}  # List to store all results
    for txt_file, ply_file in zip(upd_txt_file_list, pc_ply_list):
        try:
            with open(txt_file, 'r') as f:
                prompt = f.read().strip()
            chat_state = CONV_VISION.copy()#Clear chat_state and add only the prompt
            # Perform inference using the model
            pc_list = []
            chat.upload_pc_v2(chat_state, )
            _, pc_list = chat.encoder_pc_file(ply_file, pc_list)
            chat.ask(prompt, chat_state)
            llm_message = chat.answer(
                conv=chat_state,
                pc_list=pc_list,
                num_beams=num_beams,
                temperature=temperature,
                max_new_tokens=max_new_tokens,
                min_length=min_length,
                max_length=max_length
            )[0]
            results.update({ply_file.hex + '@' + ply_file.scene_name.split(".")[0]: {"prompt": prompt, "response": llm_message}})
        except Exception as e:
            print(f"[ERROR] Failed to process pair ({txt_file}, {ply_file}): {e}")
    try:#Write all results to a JSON file after the loop
        with open('inference_results_MiniGPT-3D_' + upd_version_name + '_' + upd_subset_type + '.json', 'w') as f:
            json.dump(results, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Failed to write results to JSON file: {e}")

def start_chat():
    print("[INFO] Starting conversation...")
    title = """<h1 align="center">Batch Process Samples With MiniGPT-3D</h1>"""
    description = """
                ##### Usage:
                1. Set the settings.
                2. Upload a .txt file with names of the scenes you want to process, one name per line.
                3. Confirm the names parsed as as you expect.
                4. Enter the absolute path to the point cloud folder.
                5. Enter the absolute path to the UPD folder.
                6. Click "Run Inference!" to start processing.
                    """
    while True:
        with gr.Blocks() as demo:
            gr.Markdown(title)
            gr.Markdown(
                """
                [[Project Page](https://tangyuan96.github.io/minigpt_3d_project_page/)]   [[Paper](https://arxiv.org/pdf/2405.01413)]   [[Code](https://github.com/TangYuan96/MiniGPT-3D)]
                """
            )
            gr.Markdown(description)
            with gr.Row():
                with gr.Column():
                    with gr.Accordion("Settings", open=True):
                        with gr.Row():
                            num_beams = gr.Slider(
                                minimum=1, maximum=10, value=1, step=1, interactive=True, label="beam number", )
                            temperature = gr.Slider(
                                minimum=0.1, maximum=2.0, value=0.2, step=0.1, interactive=True, label="Temperature", )
                        with gr.Row():
                            max_new_tokens = gr.Slider(
                                minimum=10, maximum=200, value=60, step=10, interactive=True, label="Max words per reply", )
                            max_length = gr.Slider(
                                minimum=400, maximum=1500, value=400, step=100, interactive=True,
                                label="Max words in conv.", )
                        min_length = gr.Slider(
                            minimum=1, maximum=200, value=1, step=5, interactive=True, label="Min words per reply", )
                with gr.Column():
                    file_input = gr.File(label="Upload .txt with names", file_types=[".txt"])
                    output = gr.Textbox(label="Names parsed", lines=10)
                    file_input.change(fn=process_txt, inputs=file_input, outputs=output)
                    pc_path_input = gr.Textbox(label="Point Cloud Path e.g. /gscratch/melgin/3d-grand_unzipped/3D-FRONT", placeholder="Enter the absolute point cloud folder path", interactive=True)
                    txt_path_input = gr.Textbox(label="UPD Path e.g. /project/3dllms/melgin/UPD-3D/upd_text/v1/standard", placeholder="Enter the absolute UPD folder path", interactive=True)
                    btn = gr.Button("Run Inference!")
                    out = gr.Textbox(label="Feedback (if any)")
                    btn.click(
                        fn=inference,
                        inputs=[pc_path_input, txt_path_input, num_beams, temperature, max_new_tokens, max_length, min_length],
                        outputs=out
                    )
            gr.Markdown(
                """
                #### Acknowledgements
                 [[PointLLM](https://github.com/OpenRobotLab/PointLLM/tree/master)] [[TinyGPT-V](https://github.com/DLYuanGod/TinyGPT-V)] [[MiniGPT-4](https://github.com/Vision-CAIR/MiniGPT-4)]
                """
            )
        demo.launch(share=False)
        demo.queue()

if __name__ == "__main__":
    start_chat()