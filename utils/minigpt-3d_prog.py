import argparse
import torch
from transformers import StoppingCriteriaList
from minigpt4.common.config import Config
from minigpt4.common.registry import registry
from minigpt4.conversation.conversation import Chat, CONV_VISION_Vicuna0, CONV_VISION_LLama2, CONV_VISION, \
    StoppingCriteriaSub
import os
import json

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

def inference(pcl_list_txt_file_path, upd_text_folder_subfolder_path, unzipped_point_cloud_path):
    with open(pcl_list_txt_file_path, 'r') as f:
        indentifier_at_scene_list = f.read().splitlines()
    pcl_list_txt_filename_noext = os.path.basename(os.path.normpath(pcl_list_txt_file_path)).replace('.txt', '')

    if not os.path.isdir(unzipped_point_cloud_path):
        error_message = f"Error: '{unzipped_point_cloud_path}' is not a valid folder path."
        print(error_message)
        return error_message
    if not os.path.isdir(upd_text_folder_subfolder_path):
        error_message = f"Error: '{upd_text_folder_subfolder_path}' is not a valid folder path."
        print(error_message)
        return error_message
    pc_ply_list = make_named_ply_files(indentifier_at_scene_list, unzipped_point_cloud_path)
    upd_txt_file_list = make_named_upd_txt_files(indentifier_at_scene_list, upd_text_folder_subfolder_path)
    upd_subset_type = os.path.basename(os.path.normpath(upd_text_folder_subfolder_path))

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
        json_filename = 'inference_results_MiniGPT-3D_' + pcl_list_txt_filename_noext + '_' + upd_subset_type + '.json'
        with open(json_filename, 'w') as f:
            json.dump(results, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Failed to write results to JSON file: {e}")

def programmatic_run(
        upd_text_folder_path,
        upd_version_name,
        upd_version_name_subfolder,
        unzipped_point_cloud_path,
        pcl_list_txt_file_path):
    upd_text_version_subfolder_path = os.path.join(
        upd_text_folder_path,
        upd_version_name,
        upd_version_name_subfolder)
    inference(pcl_list_txt_file_path, upd_text_version_subfolder_path, unzipped_point_cloud_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Programmatic evaluation code for MiniGPT-3D")
    parser.add_argument("--cfg-path", default="./eval_configs/MiniGPT_3D_conv_UI_demo.yaml",
                        help="path to configuration file.")
    parser.add_argument("--gpu-id", type=int, default=0, help="specify the gpu to load the model.")
    parser.add_argument("--upd_text_folder_path", type=str, required=True, help="Path to the upd_text/ folder.")
    parser.add_argument("--upd_version_name", type=str, required=False, help="Name of the upd version (e.g., 'v1').", default="3D-FRONT")
    parser.add_argument("--upd_version_name_subfolder", type=str, required=True, help="Subfolder name for the upd version (e.g., 'standard').")
    parser.add_argument("--unzipped_point_cloud_path", type=str, required=True, help="Path to the unzipped point cloud folder containing dirs identifier/scene/scene.ply")
    parser.add_argument("--pcl_list_txt_file_path", type=str, required=True, help="Path to the text file containing point cloud identifiers and scene names.")
    args = parser.parse_args()

    #Check that the passed paths are valid
    if not os.path.isdir(args.upd_text_folder_path):
        raise ValueError(f"Error: '{args.upd_text_folder_path}' is not a valid folder path.")
    if not os.path.isdir(os.path.join(args.upd_text_folder_path, args.upd_version_name, args.upd_version_name_subfolder)):
        raise ValueError(f"Error: '{os.path.join(args.upd_text_folder_path, args.upd_version_name, args.upd_version_name_subfolder)}' is not a valid folder path.")
    if not os.path.isdir(args.unzipped_point_cloud_path):
        raise ValueError(f"Error: '{args.unzipped_point_cloud_path}' is not a valid folder path.")
    if not os.path.isfile(args.pcl_list_txt_file_path):
        raise ValueError(f"Error: '{args.pcl_list_txt_file_path}' is not a valid file path.")

    conv_dict = {'pretrain_vicuna0': CONV_VISION_Vicuna0,
                'pretrain_llama2': CONV_VISION_LLama2,
                'pretrain': CONV_VISION}

    cfg = Config(args)

    model_config = cfg.model_cfg
    model_config.device_8bit = args.gpu_id
    model_cls = registry.get_model_class(model_config.arch)
    model = model_cls.from_config(model_config).to(f'cuda:{args.gpu_id}')

    CONV_VISION = conv_dict[model_config.model_type]

    stop_words_ids = [[835], [2277, 29937]]
    stop_words_ids = [torch.tensor(ids).to(device=f'cuda:{args.gpu_id}') for ids in stop_words_ids]
    stopping_criteria = StoppingCriteriaList([StoppingCriteriaSub(stops=stop_words_ids)])

    chat = Chat(model, device=f'cuda:{args.gpu_id}', stopping_criteria=stopping_criteria)

    programmatic_run(
        upd_text_folder_path=args.upd_text_folder_path,
        upd_version_name=args.upd_version_name,
        upd_version_name_subfolder=args.upd_version_name_subfolder,
        unzipped_point_cloud_path=args.unzipped_point_cloud_path,
        pcl_list_txt_file_path=args.pcl_list_txt_file_path
    )