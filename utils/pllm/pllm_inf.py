"""File to run PointLLM inference programmatically for batch evaluation."""

#pointllm/eval/pllm_inf.py

import argparse
from transformers import AutoTokenizer
import torch
import os
from pointllm.conversation import conv_templates, SeparatorStyle
from pointllm.utils import disable_torch_init
from pointllm.model import *
from pointllm.model.utils import KeywordsStoppingCriteria
import numpy as np
import json
from pointllm.data import pc_norm, farthest_point_sample
import open3d as o3d

# Suppress transformers logging errors
import logging
logging.getLogger('transformers').setLevel(logging.ERROR)

class FakeUpload:
    """
    A simple container class to mimic file upload objects for point cloud inference.
    The original PointLLM gradio code this file is based on only ever used file
    upload objects, so this class substitutes for that to allow programmatic evaluation that does not require those file upload objects that come from the gradio UI.
    """
    def __init__(self, path, hex, scene_name):
        self.name = path
        self.hex = hex
        self.scene_name = scene_name

def make_named_upd_txt_files(identifier_at_scene_list, updtext_versionfolder_subfolder_path):
    """
    Returns a list of file paths for upd text samples based on the provided subfolder and scenes.
    """
    return [os.path.join(updtext_versionfolder_subfolder_path, name + ".txt") for name in identifier_at_scene_list]

def make_named_ply_files(identifier_at_scene_list, unzipped_point_cloud_path):
    """
    Returns a list of FakeUpload objects, each representing a point cloud file.
    """
    results = []
    for identifier_at_scene in identifier_at_scene_list:
        identifier, scene = identifier_at_scene.split('@')
        results.append(FakeUpload(os.path.join(unzipped_point_cloud_path, identifier, scene, scene + ".ply"), identifier, scene))
    return results

def load_point_cloud(file_path):
    """Load a point cloud from a PLY file and process it for model input."""
    try:
        pcd = o3d.io.read_point_cloud(file_path)
        points = np.asarray(pcd.points)  # xyz
        colors = np.asarray(pcd.colors)  # rgb, if available
        
        # If no colors, create default black colors
        if colors.size == 0:
            colors = np.zeros_like(points)
        
        # Ensure colors are in range [0, 1]
        if np.max(colors) > 1:
            colors = colors.astype(np.float32) / 255
        
        # Concatenate points and colors
        point_cloud = np.concatenate((points, colors), axis=1)
        
        # Downsample if needed
        if point_cloud.shape[0] > 8192:
            point_cloud = farthest_point_sample(point_cloud, 8192)
        
        # Normalize point cloud
        point_cloud = pc_norm(point_cloud)
        point_cloud = torch.from_numpy(point_cloud).unsqueeze_(0).to(torch.float32).cuda()
        
        return point_cloud
    except Exception as e:
        print(f"[ERROR] Failed to load point cloud {file_path}: {e}", flush=True)
        return None

def inference(
        pcl_list_txt_file_path,
        updtext_versionfolder_subfolder_path,
        unzipped_point_cloud_path,
        upd_subset_name,
        model,
        tokenizer,
        point_backbone_config,
        keywords,
        mm_use_point_start_end,
        conv_template,
        json_tag=None
    ):
    """Perform batch inference on point clouds and prompts."""
    with open(pcl_list_txt_file_path, 'r') as f:
        identifier_at_scene_list = f.read().splitlines()
    pcl_list_txt_filename_noext = os.path.basename(os.path.normpath(pcl_list_txt_file_path)).replace('.txt', '')

    pc_ply_list = make_named_ply_files(identifier_at_scene_list, unzipped_point_cloud_path)
    upd_txt_file_list = make_named_upd_txt_files(identifier_at_scene_list, updtext_versionfolder_subfolder_path)

    results = {}  # Dictionary to store all results
    
    # Extract model configuration
    point_token_len = point_backbone_config['point_token_len']
    default_point_patch_token = point_backbone_config['default_point_patch_token']
    default_point_start_token = point_backbone_config['default_point_start_token']
    default_point_end_token = point_backbone_config['default_point_end_token']
    
    total_samples = len(pc_ply_list)
    for idx, (ply_file, txt_file) in enumerate(zip(pc_ply_list, upd_txt_file_list), 1):
        try:
            print(f"[PROGRESS] Processing sample {idx}/{total_samples}: {ply_file.hex}@{ply_file.scene_name}", flush=True)
            # Read prompt
            with open(txt_file, 'r') as f:
                prompt = f.read().strip()

            # Load and process point cloud
            point_clouds = load_point_cloud(ply_file.name)
            if point_clouds is None:
                print(f"[ERROR] Failed to load point cloud: {ply_file.name}", flush=True)
                continue

            # Reset conversation
            conv = conv_template.copy()
            
            # Add point tokens to the prompt
            if mm_use_point_start_end:
                prompt = default_point_start_token + default_point_patch_token * point_token_len + default_point_end_token + '\n' + prompt
            else:
                prompt = default_point_patch_token * point_token_len + '\n' + prompt

            # Add to conversation
            conv.append_message(conv.roles[0], prompt)
            conv.append_message(conv.roles[1], None)
            prompt_formatted = conv.get_prompt()

            # Tokenize
            inputs = tokenizer([prompt_formatted])
            input_ids = torch.as_tensor(inputs.input_ids).cuda()

            # Set up stopping criteria
            stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)
            stop_str = keywords[0]

            # Generate response
            with torch.inference_mode():
                output_ids = model.generate(
                    input_ids,
                    point_clouds=point_clouds,
                    do_sample=False,
                    temperature=0.2,
                    max_new_tokens=60,
                    min_length=1,
                    max_length=400,
                    stopping_criteria=[stopping_criteria]
                )

            # Decode response
            input_token_len = input_ids.shape[1]
            outputs = tokenizer.batch_decode(output_ids[:, input_token_len:], skip_special_tokens=True)[0]
            outputs = outputs.strip()
            if outputs.endswith(stop_str):
                outputs = outputs[:-len(stop_str)]
            outputs = outputs.strip()

            # Store result
            results[ply_file.hex + '@' + ply_file.scene_name.split(".")[0]] = {
                "prompt": prompt, 
                "response": outputs
            }

            print(f"[INFO] Processed {ply_file.hex}@{ply_file.scene_name}: {outputs}", flush=True)

        except Exception as e:
            print(f"[ERROR] Failed to process pair ({txt_file}, {ply_file.name}): {e}", flush=True)

    # Write all results to a JSON file
    try:
        tag_part = f"{json_tag}_" if json_tag else ""
        json_filename = f'inf_rslts_pllm_{tag_part}{pcl_list_txt_filename_noext}_{upd_subset_name}.json'
        with open(json_filename, 'w') as f:
            json.dump(results, f, indent=4)
        print(f"[INFO] Results saved to {json_filename}", flush=True)
    except Exception as e:
        print(f"[ERROR] Failed to write results to JSON file: {e}", flush=True)

def init_model(args):
    """Initialize the model for batch inference."""
    # Model
    disable_torch_init()
    model_name = os.path.expanduser(args.model_name)

    print(f'[INFO] Model name: {os.path.basename(model_name)}', flush=True)

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = PointLLMLlamaForCausalLM.from_pretrained(model_name, low_cpu_mem_usage=False, use_cache=True).cuda()
    model.initialize_tokenizer_point_backbone_config_wo_embedding(tokenizer)

    model.eval()

    mm_use_point_start_end = getattr(model.config, "mm_use_point_start_end", False)
    # Add special tokens ind to model.point_config
    point_backbone_config = model.get_model().point_backbone_config
    
    conv = conv_templates["vicuna_v1_1"].copy()

    stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
    keywords = [stop_str]
    
    return model, tokenizer, point_backbone_config, keywords, mm_use_point_start_end, conv

def existing_dir(path):
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"readable_dir: '{path}' is not a valid directory")
    return path

def existing_file(path):
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError(f"readable_file: '{path}' is not a valid file")
    return path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Programmatic evaluation code for PointLLM")
    parser.add_argument("--model_name", type=str, default="RunsenXu/PointLLM_7B_v1.2",
                        help="Path to the PointLLM model")
    parser.add_argument("--upd_text_folder_path", type=existing_dir, required=True, 
                        help="Path to the upd_text/ folder.")
    parser.add_argument("--upd_version_name", type=str, required=True, 
                        help="Name of the upd version (e.g., 'Crops3D_gpt-5-nano').")
    parser.add_argument("--upd_version_name_subfolder", type=str, required=True, 
                        help="Subfolder name for the upd version (e.g., 'standard').")
    parser.add_argument("--unzipped_point_cloud_path", type=existing_dir, required=True, 
                        help="Path to the unzipped point cloud folder containing dirs identifier/scene/scene.ply")
    parser.add_argument("--pcl_list_txt_file_path", type=existing_file, required=True, 
                        help="Path to the text file containing point cloud identifiers and scene names.")
    parser.add_argument("--json_tag", type=str, required=False, 
                        help="Optional tag to include in the output JSON filename, eg 'ft-comb' for finetune-combined", 
                        default=None)
    args = parser.parse_args()

    # Check that the passed paths are valid
    updtext_versionfolder_subfolder_path = os.path.join(
        args.upd_text_folder_path,
        args.upd_version_name,
        args.upd_version_name_subfolder
    )
    if not os.path.isdir(updtext_versionfolder_subfolder_path):
        raise ValueError(f"Error: '{updtext_versionfolder_subfolder_path}' is not a valid folder path.")

    # Initialize model
    model, tokenizer, point_backbone_config, keywords, mm_use_point_start_end, conv = init_model(args)

    # Run batch inference
    inference(
        pcl_list_txt_file_path=args.pcl_list_txt_file_path,
        updtext_versionfolder_subfolder_path=updtext_versionfolder_subfolder_path,
        unzipped_point_cloud_path=args.unzipped_point_cloud_path,
        upd_subset_name=args.upd_version_name_subfolder,
        model=model,
        tokenizer=tokenizer,
        point_backbone_config=point_backbone_config,
        keywords=keywords,
        mm_use_point_start_end=mm_use_point_start_end,
        conv_template=conv,
        json_tag=args.json_tag
    )