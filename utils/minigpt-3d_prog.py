import argparse
import torch
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
    parser.add_argument("--folder", type=str, required=True, help="Folder name to run inference on")
    args = parser.parse_args()
    return args

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
    with open(file.name, 'r') as f:
        names_list = f.read().splitlines()
    upd_version_name = os.path.basename(os.path.normpath(file.name)).replace('.txt', '')
    return names_list, upd_version_name

def process_txt_from_path(file_path):
    """
    Overload of process_txt that takes a raw file path string instead of a file object.
    For programmatic runs
    """
    with open(file_path, 'r') as f:
        names_list = f.read().splitlines()
    upd_version_name = os.path.basename(os.path.normpath(file_path)).replace('.txt', '')
    return names_list, upd_version_name

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

def inference(pc_path, txt_path, names_list):
    if not os.path.isdir(pc_path):
        error_message = f"Error: '{pc_path}' is not a valid folder path."
        print(error_message)
        return error_message
    if not os.path.isdir(txt_path):
        error_message = f"Error: '{txt_path}' is not a valid folder path."
        print(error_message)
        return error_message
    pc_ply_list = make_named_ply_files(names_list, pc_path)
    upd_txt_file_list = make_named_upd_txt_files(names_list, txt_path)
    upd_subset_type = os.path.basename(os.path.normpath(txt_path))

    if not upd_txt_file_list or not pc_ply_list:
        print("[ERROR] upd_txt_file_list or pc_ply_list is empty. Please process the input files first.")
        return

    results = {}  # List to store all results

    # Only process pairs where the name is in allowed_names (if provided)
    for txt_file, ply_file in zip(upd_txt_file_list, pc_ply_list):

        try:
            with open(txt_file, 'r') as f:
                prompt = f.read().strip()

            # Clear chat_state and add only the prompt
            chat_state = CONV_VISION.copy()

            # Perform inference using the model
            pc_list = []
            chat.upload_pc_v2(chat_state, )
            _, pc_list = chat.encoder_pc_file(ply_file, pc_list)
            chat.ask(prompt, chat_state)
            llm_message = chat.answer(conv=chat_state,
                                      pc_list=pc_list,
                                      num_beams=1,
                                      temperature=0.2,
                                      max_new_tokens=60,
                                      min_length=1,
                                      max_length=400)[0]

            results.update({ply_file.hex + '@' + ply_file.scene_name.split(".")[0]: {"prompt": prompt, "response": llm_message}})

        except Exception as e:
            print(f"[ERROR] Failed to process pair ({txt_file}, {ply_file}): {e}")

    # Write all results to a JSON file after the loop
    try:
        json_filename = 'inference_results_MiniGPT-3D_' + upd_version_name + '_' + upd_subset_type + '.json'
        with open(json_filename, 'w') as f:
            json.dump(results, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Failed to write results to JSON file: {e}")

def programmatic_run(folder):
    print("running programmatic inference...")
    upd_text_path = os.path.join("/project/3dllms/melgin/UPD-3D/upd_text/3D-FRONT/", folder)
    # point_cloud_path = "/cluster/medbow/home/melgin/tmp_candelete/3D-Front_test"
    point_cloud_path = "/gscratch/melgin/3d-grand_unzipped/3D-FRONT"
    pcl_list_path = "/project/3dllms/melgin/UPD-3D/pcl_lists/3D-FRONT_test.txt"
    names_list, upd_version_name = process_txt_from_path(pcl_list_path)
    inference(point_cloud_path, upd_text_path)

if __name__ == "__main__":
    folder = args.folder
    print(f"Running inference for folder: {folder}")
    programmatic_run(folder)