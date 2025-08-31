"""File to run MiniGPT-3D inference programmatically.

Updated to robustly handle PLY files with Crops3D-style headers/types,
mirroring the logic in gplm_inf_upd.py. We parse the PLY directly and
prepare the point cloud embedding without relying on Open3D, so both
3D-FRONT and Crops3D variants are supported.
"""

import argparse
import torch
import numpy as np
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

def _load_ply_points_rgb(ply_file_path):
    """
    Robustly load a binary_little_endian PLY file and return an array of shape (N, 6)
    with columns [x, y, z, r, g, b]. Supports common variations:
      - x,y,z as float/double; colors as uchar/short/float, names red/green/blue or r/g/b.
    If colors are missing, fills zeros. Samples/pads to 8192 points.

    Returns a numpy.float32 array with RGB in [0, 255].
    """
    # Map PLY scalar types to numpy dtypes
    ply_to_np = {
        'char': 'i1', 'uchar': 'u1', 'int8': 'i1', 'uint8': 'u1',
        'short': 'i2', 'ushort': 'u2', 'int16': 'i2', 'uint16': 'u2',
        'int': 'i4', 'uint': 'u4', 'int32': 'i4', 'uint32': 'u4',
        'float': 'f4', 'float32': 'f4', 'double': 'f8', 'float64': 'f8'
    }

    with open(ply_file_path, 'rb') as f:
        format_str = None
        vertex_count = None
        vertex_props = []
        in_vertex_props = False

        # Parse header
        while True:
            line = f.readline()
            if not line:
                raise ValueError(f"Unexpected EOF while reading PLY header: {ply_file_path}")
            line = line.decode('utf-8', errors='ignore').strip()
            if line.startswith('format'):
                parts = line.split()
                if len(parts) >= 2:
                    format_str = parts[1].lower()
            elif line.startswith('element'):
                parts = line.split()
                if len(parts) >= 3 and parts[1].lower() == 'vertex':
                    vertex_count = int(parts[2])
                    in_vertex_props = True
                else:
                    in_vertex_props = False
            elif line.startswith('property') and in_vertex_props:
                parts = line.split()
                if len(parts) >= 3:
                    ptype = parts[1].lower()
                    pname = parts[2].lower()
                    vertex_props.append((pname, ptype))
            elif line == 'end_header':
                break

        if format_str != 'binary_little_endian':
            raise NotImplementedError(
                f"Only binary_little_endian PLY is supported, got '{format_str}' for {ply_file_path}"
            )
        if vertex_count is None or vertex_count <= 0 or not vertex_props:
            raise ValueError(f"Invalid PLY header: missing vertex element/properties in {ply_file_path}")

        # Structured dtype
        dtype_fields = []
        for pname, ptype in vertex_props:
            np_type = ply_to_np.get(ptype)
            if np_type is None:
                raise ValueError(
                    f"Unsupported PLY property type '{ptype}' for field '{pname}' in {ply_file_path}"
                )
            dtype_fields.append((pname, np_type))
        dtype = np.dtype(dtype_fields)

        # Read binary payload
        bytes_needed = dtype.itemsize * vertex_count
        raw = f.read(bytes_needed)
        if len(raw) < bytes_needed:
            raise ValueError(
                f"PLY binary payload too small: expected {bytes_needed} bytes, got {len(raw)} in {ply_file_path}"
            )
        data = np.frombuffer(raw, dtype=dtype, count=vertex_count)

    names = set(data.dtype.names or [])
    for coord in ('x', 'y', 'z'):
        if coord not in names:
            raise ValueError(f"Missing '{coord}' in PLY vertex properties for {ply_file_path}")

    x = data['x'].astype(np.float32)
    y = data['y'].astype(np.float32)
    z = data['z'].astype(np.float32)

    def pick_color(name_primary, name_alt):
        if name_primary in names:
            arr = data[name_primary]
        elif name_alt in names:
            arr = data[name_alt]
        else:
            arr = None
        return arr

    r_arr = pick_color('red', 'r')
    g_arr = pick_color('green', 'g')
    b_arr = pick_color('blue', 'b')

    if r_arr is None or g_arr is None or b_arr is None:
        r = np.zeros_like(x, dtype=np.float32)
        g = np.zeros_like(y, dtype=np.float32)
        b = np.zeros_like(z, dtype=np.float32)
    else:
        def normalize_color(arr):
            if np.issubdtype(arr.dtype, np.floating):
                arrf = arr.astype(np.float32)
                maxv = float(np.nanmax(arrf)) if arrf.size > 0 else 0.0
                if maxv <= 1.0:
                    arrf = arrf * 255.0
                return np.clip(arrf, 0.0, 255.0)
            elif np.issubdtype(arr.dtype, np.signedinteger) or np.issubdtype(arr.dtype, np.unsignedinteger):
                arrf = arr.astype(np.float32)
                return np.clip(arrf, 0.0, 255.0)
            else:
                return np.clip(arr.astype(np.float32), 0.0, 255.0)

        r = normalize_color(r_arr)
        g = normalize_color(g_arr)
        b = normalize_color(b_arr)

    pts = np.stack([x, y, z, r, g, b], axis=1)

    N = pts.shape[0]
    target = 8192
    if N > target:
        idx = np.random.choice(N, size=target, replace=False)
        pts = pts[idx]
    elif N < target and N > 0:
        pad_size = target - N
        pad_idx = np.random.choice(N, size=pad_size, replace=True)
        pts = np.concatenate([pts, pts[pad_idx]], axis=0)
    elif N == 0:
        raise ValueError(f"No vertices found in {ply_file_path}")

    return pts.astype(np.float32)

def make_named_upd_txt_files(identifier_at_scene_list, updtext_versionfolder_subfolder_path):
    """
    Returns a list of file paths for upd text samples based on the provided subfolder and scenes.
    """
    return [os.path.join(updtext_versionfolder_subfolder_path, name + ".txt") for name in identifier_at_scene_list]

def make_named_ply_files(identifier_at_scene_list, unzipped_point_cloud_path):
    """
    Returns a list of FakeUpload objects, each representing a point cloud file.
    Prefers 3D-FRONT layout (identifier/scene/scene.ply); falls back to
    Crops3D-like layout (identifier/scene.ply) if the first path doesn't exist.
    """
    results = []
    for identifier_at_scene in identifier_at_scene_list:
        identifier, scene = identifier_at_scene.split('@')
        front_path = os.path.join(unzipped_point_cloud_path, identifier, scene, scene + ".ply")
        crops3d_path = os.path.join(unzipped_point_cloud_path, identifier, scene + ".ply")
        chosen = front_path if os.path.isfile(front_path) else crops3d_path
        results.append(FakeUpload(chosen, identifier, scene))
    return results

def _prepare_pc_embedding(chat, ply_path):
    """
    Load PLY robustly (Crops3D/3D-FRONT), normalize/colors to [0,1], sample if needed,
    and encode via chat.model.encode_pc. Returns the pc embedding tensor.
    """
    pts = _load_ply_points_rgb(ply_path)  # (N,6) with RGB in [0,255]
    points = pts[:, :3]
    colors = pts[:, 3:6]

    # Colors to [0,1]
    colors = np.clip(colors, 0.0, 255.0) / 255.0
    point_cloud = np.concatenate([points, colors], axis=1).astype(np.float32)

    # Match Chat.encoder_pc_file sampling behavior
    if 8192 < point_cloud.shape[0]:
        indices = np.random.permutation(point_cloud.shape[0])[:2048]
        point_cloud = point_cloud[indices]
    else:
        # Warn-like behavior can be printed if desired
        pass

    # Normalize using Chat's method
    point_cloud = chat.pc_norm(point_cloud)
    pc_tensor = torch.from_numpy(point_cloud).unsqueeze(0).to(chat.device)
    pc_emb, _ = chat.model.encode_pc(pc_tensor)
    return pc_emb

def inference(
        pcl_list_txt_file_path,
        updtext_versionfolder_subfolder_path,
        unzipped_point_cloud_path,
        upd_subset_name,
        conv_vision,
        chat,
        json_tag=None
    ):
    with open(pcl_list_txt_file_path, 'r') as f:
        identifier_at_scene_list = f.read().splitlines()
    pcl_list_txt_filename_noext = os.path.basename(os.path.normpath(pcl_list_txt_file_path)).replace('.txt', '')

    pc_ply_list = make_named_ply_files(identifier_at_scene_list, unzipped_point_cloud_path)
    upd_txt_file_list = make_named_upd_txt_files(identifier_at_scene_list, updtext_versionfolder_subfolder_path)

    results = {}  # List to store all results
    for ply_file, txt_file  in zip(pc_ply_list, upd_txt_file_list):
        try:
            with open(txt_file, 'r') as f:
                prompt = f.read().strip()

            # Clear chat_state and add only the prompt
            chat_state = conv_vision.copy()

            # Prepare pc embedding robustly (no Open3D dependency)
            pc_list = []
            chat.upload_pc_v2(chat_state)
            pc_emb = _prepare_pc_embedding(chat, ply_file.name)
            pc_list.append(pc_emb)

            chat.ask(prompt, chat_state)
            llm_message = chat.answer(
                conv=chat_state,
                pc_list=pc_list,
                num_beams=1,
                temperature=0.2,
                max_new_tokens=60,
                min_length=1,
                max_length=400,
            )[0]
            results.update({
                ply_file.hex + '@' + ply_file.scene_name.split(".")[0]: {
                    "prompt": prompt,
                    "response": llm_message,
                }
            })

        except Exception as e:
            print(f"[ERROR] Failed to process pair ({txt_file}, {ply_file.name}): {e}")

    # Write all results to a JSON file after the loop
    try:
        tag_part = f"{json_tag}_" if json_tag else ""
        # Ensure output directory exists and write there
        out_dir = os.path.join(os.getcwd(), 'inf_rslts')
        os.makedirs(out_dir, exist_ok=True)
        json_filename = f'inf_rslts_mgpt3d_{tag_part}{pcl_list_txt_filename_noext}_{upd_subset_name}.json'
        out_path = os.path.join(out_dir, json_filename)
        with open(out_path, 'w') as f:
            json.dump(results, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Failed to write results to JSON file: {e}")

def existing_dir(path):
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"readable_dir: '{path}' is not a valid directory")
    return path

def existing_file(path):
    if not os.path.isfile(path):
        raise argparse.ArgumentTypeError(f"readable_file: '{path}' is not a valid file")
    return path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Programmatic evaluation code for MiniGPT-3D")
    parser.add_argument("--cfg-path", required=True,
                        help="Path to configuration file. (e.g., ./eval_configs/MiniGPT_3D_conv_UI_demo.yaml)")
    parser.add_argument("--gpu-id", type=int, default=0, help="specify the gpu to load the model.")
    parser.add_argument("--upd_text_folder_path", type=existing_dir, required=True, help="Path to the upd_text/ folder.")
    parser.add_argument("--upd_version_name", type=str, required=True, help="Name of the upd version (e.g., 'Crops3D_gpt-5-nano').")
    parser.add_argument("--upd_version_name_subfolder", type=str, required=True, help="Subfolder name for the upd version (e.g., 'standard').")
    parser.add_argument("--unzipped_point_cloud_path", type=existing_dir, required=True, help="Path to the unzipped point cloud folder containing dirs identifier/scene/scene.ply")
    parser.add_argument("--pcl_list_txt_file_path", type=existing_file, required=True, help="Path to the text file containing point cloud identifiers and scene names.")
    parser.add_argument(
        "--options",
        nargs="+",
        help="override some settings in the used config, the key-value pair in xxx=yyy format will be merged into config file (deprecate), change to --cfg-options instead."
    )
    parser.add_argument("--json_tag", type=str, required=False, help="Optional tag to include in the output JSON filename, eg 'ft-comb' for finetune-combined", default=None)
    args = parser.parse_args()

    #Check that the passed paths are valid
    updtext_versionfolder_subfolder_path=os.path.join(
        args.upd_text_folder_path,
        args.upd_version_name,
        args.upd_version_name_subfolder
    )
    if not os.path.isdir(updtext_versionfolder_subfolder_path):
        raise ValueError(f"Error: '{updtext_versionfolder_subfolder_path}' is not a valid folder path.")

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

    inference(
        pcl_list_txt_file_path=args.pcl_list_txt_file_path,
        updtext_versionfolder_subfolder_path=updtext_versionfolder_subfolder_path,
        unzipped_point_cloud_path=args.unzipped_point_cloud_path,
        upd_subset_name=args.upd_version_name_subfolder,
        conv_vision=CONV_VISION,
        chat=chat,
        json_tag=args.json_tag
    )